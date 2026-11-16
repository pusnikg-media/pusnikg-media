#!/usr/bin/env python3
"""Clipfabrik-Regression per Video-/Audio-Hash (Block 3, Fable-Nacht 16.11.2026).

Warum: Eine Aenderung an clipfabrik.py darf bestehende Layouts nicht still veraendern (native/full/framed/split + Hook).
Gerendert wird auf einer synthetischen Quelle (kein Netz). Hash = SHA-256 ueber die DEKODIERTEN Frames (ffmpeg framemd5 des
Videostroms) und ueber die dekodierten PCM-Samples des Tons. Dazu Struktur-Werte (Dauer Video/Ton, Frameanzahl) zur Sync-Pruefung.

Benutzen (vor und nach einer Aenderung, gleiche Maschine/gleicher ffmpeg-Build):
  python3 tests/clip_regression.py save  VORHER      # schreibt <tmp>/clip_regression_VORHER.json
  ... Code aendern ...
  python3 tests/clip_regression.py compare VORHER    # Exit 1 + Liste, wenn sich ein Layout veraendert hat
  python3 tests/clip_regression.py show              # nur ausgeben
Golden-Datei im Repo: tests/fixtures/clip_hashes.json (Schluessel = ffmpeg-Build-Kennung; fremder Build -> nur Struktur-Pruefung).
  python3 tests/clip_regression.py golden            # schreibt/aktualisiert den Eintrag fuer DIESEN ffmpeg-Build
Exit 0 = gleich, 1 = Abweichung, 2 = Fehler beim Rendern.
"""
import hashlib, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
from conftest import load  # noqa: E402

WORDS = [{"w": "Hello", "s": 0.6, "e": 1.0}, {"w": "this", "s": 1.1, "e": 1.4}, {"w": "is", "s": 1.5, "e": 1.7}, {"w": "a", "s": 1.8, "e": 1.9},
         {"w": "test.", "s": 2.0, "e": 2.6}, {"w": "Tom's", "s": 2.8, "e": 3.2}, {"w": "\"quoted\"", "s": 3.3, "e": 3.9}]
CAPTION = "Lacy couldn't believe Rug is too SCARED to drive his Rolls-Royce in the RAIN... 😭"
CASES = {  # Name -> Clip-Felder (alles ausser id/a/b)
    "native": {"layout": "native", "caption": CAPTION},
    "native_captions": {"layout": "native", "caption": CAPTION, "captions": True},
    "native_hook": {"layout": "native", "caption": CAPTION, "hook": [3.0, 4.0]},
    "native_special": {"layout": "native", "caption": "Tom's \"wild\" 100% moment: A&B, C:D\\E... 🔥"},
    "full": {"layout": "full", "title": "TEST TITLE"},
    "full_track": {"layout": "full", "title": "TEST: TITLE", "track": True},
    "framed": {"layout": "framed", "title": "TEST TITLE"},
    "split": {"layout": "split", "facecam": [0.70, 0.05, 0.28, 0.28], "caption": CAPTION},
    "split_auto_nocam": {"layout": "split", "facecam": "auto", "caption": CAPTION},   # synthetisch ohne Gesicht -> native-Rueckfall
}


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, **k)


def ffmpeg_id():
    first = sh("ffmpeg", "-version", text=True).stdout.split("\n")[0]
    return hashlib.sha1(first.encode()).hexdigest()[:10] + " " + first[:40]


def make_source(path, with_audio=True):
    args = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=6"]
    if with_audio: args += ["-f", "lavfi", "-i", "sine=frequency=440:duration=6"]
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"] + (["-c:a", "aac", "-shortest"] if with_audio else ["-an"]) + [path]
    r = sh(*args, text=True)
    if r.returncode: raise SystemExit("source failed: " + r.stderr)


def vhash(f):
    r = sh("ffmpeg", "-v", "error", "-i", f, "-map", "0:v:0", "-f", "framemd5", "-", text=True)
    rows = [l.rsplit(",", 1)[-1].strip() for l in r.stdout.split("\n") if l and not l.startswith("#")]
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()[:16], len(rows)


def ahash(f):
    r = sh("ffmpeg", "-v", "error", "-i", f, "-map", "0:a:0", "-f", "s16le", "-ac", "1", "-ar", "44100", "-")
    return (hashlib.sha256(r.stdout).hexdigest()[:16], len(r.stdout) / 2 / 44100) if r.stdout else (None, 0.0)


def vdur(f):
    r = sh("ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", f, text=True)
    try: return float(r.stdout.strip())
    except ValueError: return 0.0


def measure(cases=CASES):
    cf = load("pipeline/clipfabrik/clipfabrik.py", "clipfabrik_reg")
    tmp = tempfile.mkdtemp(prefix="clipreg_"); src = os.path.join(tmp, "src.mp4"); make_source(src)
    out = {"_ffmpeg": ffmpeg_id()}
    for name, fields in cases.items():
        d = os.path.join(tmp, name); os.makedirs(d)
        job = {"name": "t", "min_len": 3, "clips": [dict({"id": "x", "a": 0.5, "b": 4.5, "title": "TEST TITLE"}, **fields)]}
        p = cf.probe(src)
        err = cf.check_clips(job, p["dur"])
        if err: out[name] = {"error": err}; continue
        try: r = cf.render_clip(job, job["clips"][0], src, p, WORDS, d, tmp)
        except Exception as e: out[name] = {"error": repr(e)}; continue
        f = os.path.join(d, r["file"]); vh, nf = vhash(f); ah, adur = ahash(f); vd = vdur(f)
        out[name] = {"layout": r.get("layout"), "video": vh, "frames": nf, "audio": ah, "vdur": round(vd, 3), "adur": round(adur, 3),
                     "sync_ok": bool(ah) and abs(vd - adur) < 0.10}
    # Quelle ohne Ton: darf nicht abstuerzen (Wächter-Fall: Clip ohne Audiospur)
    src2 = os.path.join(tmp, "silent.mp4"); make_source(src2, with_audio=False); d = os.path.join(tmp, "silent"); os.makedirs(d)
    job = {"name": "t", "min_len": 3, "clips": [{"id": "x", "a": 0.5, "b": 4.5, "layout": "native", "caption": CAPTION}]}
    try:
        r = cf.render_clip(job, job["clips"][0], src2, cf.probe(src2), WORDS, d, tmp); f = os.path.join(d, r["file"])
        out["no_audio_source"] = {"layout": r.get("layout"), "video": vhash(f)[0], "frames": vhash(f)[1], "audio": ahash(f)[0]}
    except Exception as e: out["no_audio_source"] = {"error": repr(e)}
    return out


def diff(a, b):
    bad = []
    for k in sorted(set(a) | set(b)):
        if k == "_ffmpeg": continue
        if a.get(k) != b.get(k): bad.append(f"{k}: {a.get(k)}  ->  {b.get(k)}")
    return bad


def structural_problems(m):
    """Gilt auf JEDEM ffmpeg-Build: Fehler, Sync > 100 ms, falsche Frameanzahl."""
    bad = []
    for k, v in m.items():
        if k == "_ffmpeg": continue
        if "error" in v: bad.append(f"{k}: {v['error']}"); continue
        if "sync_ok" in v and not v["sync_ok"]: bad.append(f"{k}: Bild {v['vdur']} s / Ton {v['adur']} s laufen auseinander")
        if "frames" in v and not (95 <= v["frames"] <= 150): bad.append(f"{k}: {v['frames']} Frames (erwartet ca. 100-125)")
    return bad


def main(argv):
    mode = argv[1] if len(argv) > 1 else "show"
    m = measure(); tmpf = lambda n: os.path.join(tempfile.gettempdir(), f"clip_regression_{n}.json")
    for line in structural_problems(m): print("STRUKTUR:", line)
    bad_struct = bool(structural_problems(m))
    if any("error" in v for k, v in m.items() if k != "_ffmpeg"): print("RENDER_FEHLER"); return 2
    if mode == "save":
        json.dump(m, open(tmpf(argv[2]), "w"), indent=1); print("gespeichert", tmpf(argv[2])); return 0
    if mode == "compare":
        old = json.load(open(tmpf(argv[2]))); bad = diff(old, m)
        print("GLEICH (alle Hashes identisch)" if not bad else "ABWEICHUNG:\n  " + "\n  ".join(bad)); return 1 if (bad or bad_struct) else 0
    gp = os.path.join(HERE, "fixtures", "clip_hashes.json")
    gold = json.load(open(gp)) if os.path.exists(gp) else {}
    key = m["_ffmpeg"]
    if mode == "golden":
        gold[key] = {k: v for k, v in m.items() if k != "_ffmpeg"}; json.dump(gold, open(gp, "w"), indent=1, sort_keys=True); print("Golden aktualisiert fuer", key); return 0
    if mode == "check":
        if key not in gold: print("kein Golden fuer diesen ffmpeg-Build (", key, ") - nur Struktur geprueft"); return 1 if bad_struct else 0
        bad = diff(gold[key], m); print("GLEICH" if not bad else "ABWEICHUNG:\n  " + "\n  ".join(bad)); return 1 if (bad or bad_struct) else 0
    print(json.dumps(m, indent=1)); return 1 if bad_struct else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
