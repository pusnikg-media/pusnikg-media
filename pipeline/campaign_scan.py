"""Pusnik G campaign scanner (0 credits): find the strongest clip segments in an official campaign video.
Usage: python3 pipeline/campaign_scan.py src.mp4 outdir [n=6] [min_len=12] [max_len=22]
Writes outdir/candidates.json (start, end, score, cuts, speech text) and outdir/cand_XX.jpg contact sheets
(4 frames per candidate) so the agent can LOOK at each candidate with Read and write an honest top_text.
Then render the picked ones with campaign_clip.py (job: src, out, start, end, top_text, logo, captions).
Scoring: loud/energetic audio + many scene cuts + speech that starts and ends on sentence boundaries;
skips the first 3 s (logos) and the last 8 s (end cards / ratings); candidates never overlap."""
import json, os, re, subprocess, sys
import numpy as np


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("FAIL: " + " ".join(cmd)[:200] + "\n" + r.stderr[-1200:])
    return r


def duration(src):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]).stdout.strip())


def scene_cuts(src):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-an", "-vf", "select='gt(scene,0.32)',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def energy(src, tmp):
    wav = os.path.join(tmp, "scan.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav])
    import scipy.io.wavfile as wavf
    _, a = wavf.read(wav)
    a = a.astype(np.float32) / 32768 if a.dtype == np.int16 else a.astype(np.float32)
    hop = 8000  # 0.5 s
    e = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2) + 1e-9) for i in range(0, max(len(a) - hop, 1), hop)])
    return wav, a, 20 * np.log10(e + 1e-9)


def speech(a):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return []
    m = WhisperModel(os.environ.get("WHISPER_MODEL", "base.en"), device="cpu", compute_type="int8")
    segs, _ = m.transcribe(a, vad_filter=True, beam_size=3)
    return [(s.start, s.end, s.text.strip()) for s in segs if s.text.strip()]


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, out = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    lo = float(sys.argv[4]) if len(sys.argv) > 4 else 12.0
    hi = float(sys.argv[5]) if len(sys.argv) > 5 else 22.0
    os.makedirs(out, exist_ok=True)
    dur = duration(src)
    if dur < lo + 11:
        sys.exit(f"source too short ({dur:.1f}s)")
    cuts = scene_cuts(src)
    wav, a, edb = energy(src, out)
    segs = speech(a)
    os.remove(wav)
    # candidate starts: scene cuts + speech starts (+ a 2 s grid as fallback), inside the safe zone
    t0, t1 = 3.0, dur - 8.0
    starts = sorted(set([round(c, 2) for c in cuts] + [round(s[0], 2) for s in segs] + list(np.arange(t0, t1, 2.0).round(2))))
    starts = [s for s in starts if t0 <= s <= t1 - lo]
    ends_pref = [s[1] for s in segs]
    emax, emin = float(np.max(edb)), float(np.percentile(edb, 10))
    cands = []
    for s in starts:
        # prefer an end on a sentence boundary inside [lo, hi]; otherwise the next cut; otherwise s+lo+4
        opts = [e for e in ends_pref if lo <= e - s <= hi] or [c for c in cuts if lo <= c - s <= hi] or [min(s + lo + 4, t1)]
        e = min(max(opts), t1)
        if e - s < lo:
            continue
        i0, i1 = int(s * 2), max(int(e * 2), int(s * 2) + 1)
        en = float(np.mean(edb[i0:i1])); en_n = (en - emin) / max(emax - emin, 1e-3)
        nc = sum(1 for c in cuts if s < c < e); cut_n = min(nc / ((e - s) / 2.0), 1.0)  # 1 cut per 2 s = max
        sp = [x for x in segs if x[0] < e and x[1] > s]
        clean = 1.0 if (not sp or (abs(sp[0][0] - s) < 0.6 and abs(sp[-1][1] - e) < 0.8)) else 0.4
        score = 0.45 * en_n + 0.35 * cut_n + 0.2 * clean
        cands.append({"start": round(s, 2), "end": round(e, 2), "len": round(e - s, 1), "score": round(score, 3),
                      "cuts": nc, "speech": " ".join(x[2] for x in sp)[:300]})
    cands.sort(key=lambda c: -c["score"])
    pick = []
    for c in cands:
        if all(c["end"] <= p["start"] - 1 or c["start"] >= p["end"] + 1 for p in pick):
            pick.append(c)
        if len(pick) >= n:
            break
    pick.sort(key=lambda c: c["start"])
    for i, c in enumerate(pick):
        sheet = os.path.join(out, f"cand_{i:02d}.jpg"); c["sheet"] = sheet
        ts = [c["start"] + (c["end"] - c["start"]) * f for f in (0.05, 0.35, 0.65, 0.95)]
        frames = []
        for k, t in enumerate(ts):
            fp = os.path.join(out, f"_f{i}_{k}.jpg")
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=480:-2", fp])
            frames.append(fp)
        run(["ffmpeg", "-y", "-v", "error", *sum([["-i", f] for f in frames], []), "-filter_complex",
             f"hstack=inputs={len(frames)}", sheet])
        for f in frames:
            os.remove(f)
    json.dump({"src": src, "duration": round(dur, 1), "candidates": pick}, open(os.path.join(out, "candidates.json"), "w"), indent=1)
    for i, c in enumerate(pick):
        print(f"cand_{i:02d}: {c['start']:.1f}-{c['end']:.1f}s score={c['score']} cuts={c['cuts']} | {c['speech'][:90]}")
    print(f"SCAN_OK {len(pick)} candidates -> {out}/candidates.json")


if __name__ == "__main__":
    main()
