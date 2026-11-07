"""Pusnik G preflight: validate a job.json in seconds, before the expensive render.
Usage: python3 pipeline/preflight.py job.json
Checks: vo_dir/timing.json + line wavs, shots count == script lines, every clip exists, decodes (ffprobe)
and is long enough for its start + slot, music exists/decodes, card.line in range, punch stems match,
total length 18-35 s, out writable. Prints PREFLIGHT_OK, or PREFLIGHT_FAIL + one line per problem (exit 1).
Paths in job.json are relative to the job.json folder (same rule as render_hf.py)."""
import json, os, re, subprocess, sys

GAP, TAIL = 0.22, 0.6
MIN_S, MAX_S = 18.0, 35.0


def probe(f):
    """(duration, has_video, has_audio) or None if ffprobe can't decode it."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                        "-of", "json", f], capture_output=True, text=True)
    if r.returncode:
        return None
    try:
        d = json.loads(r.stdout)
        types = {s.get("codec_type") for s in d.get("streams", [])}
        return float(d.get("format", {}).get("duration") or 0), "video" in types, "audio" in types
    except (ValueError, KeyError):
        return None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    jp = os.path.abspath(sys.argv[1]); base = os.path.dirname(jp); P, W = [], []
    ap = lambda p: p if os.path.isabs(p) else os.path.join(base, p)
    try:
        job = json.load(open(jp))
    except (OSError, ValueError) as e:
        print(f"PREFLIGHT_FAIL\n- job.json unreadable: {e}"); sys.exit(1)
    for k in ("vo_dir", "shots", "out"):
        if k not in job: P.append(f"job.json: missing key '{k}'")
    if "day" not in job and "hook_big" not in job: P.append("job.json: missing 'day' (or 'hook_big')")
    if P:
        print("PREFLIGHT_FAIL\n" + "\n".join("- " + p for p in P)); sys.exit(1)
    vo = ap(job["vo_dir"]); tj = os.path.join(vo, "timing.json"); timing = []
    try:
        timing = json.load(open(tj))
    except (OSError, ValueError) as e:
        P.append(f"{tj}: missing/invalid ({e.__class__.__name__}) - run tts.py first")
    for i, ln in enumerate(timing):
        f = ln.get("file", "")
        if not os.path.exists(f) and not os.path.exists(os.path.join(vo, os.path.basename(f))):
            P.append(f"voice line {i}: wav missing ({f})")
        if not ln.get("dur", 0) > 0.3: P.append(f"voice line {i}: duration {ln.get('dur')} s too short")
        if len(ln.get("text", "").split()) == 0: P.append(f"voice line {i}: empty text")
    shots = job.get("shots") or []
    if timing and len(shots) != len(timing):
        P.append(f"shots: {len(shots)} shot lists but {len(timing)} script lines (need exactly one list per line)")
    # line windows exactly like build_cd.py
    wins, t = [], 0.0
    for i, ln in enumerate(timing):
        wins.append((t, t + ln.get("dur", 0))); t += ln.get("dur", 0) + (GAP if i < len(timing) - 1 else 0)
    total = t + TAIL
    if timing and not MIN_S <= total <= MAX_S:
        P.append(f"length: {total:.1f} s outside {MIN_S:.0f}-{MAX_S:.0f} s - shorten/lengthen the script")
    stems, cache = {}, {}
    for i, line in enumerate(shots):
        if not isinstance(line, list) or not line:
            P.append(f"shots[{i}]: empty - every line needs at least one clip"); continue
        slot = None
        if i < len(wins):
            b = wins[i + 1][0] if i + 1 < len(wins) else total
            slot = (b - wins[i][0]) / len(line)
            if slot > 2.6: W.append(f"shots[{i}]: {slot:.2f} s per cut (> 2.3 s rule) - add a clip to this line")
        for c in line:
            if not isinstance(c, dict) or "file" not in c:
                P.append(f"shots[{i}]: entry {c!r} has no 'file'"); continue
            f = ap(c["file"]); stem = os.path.splitext(os.path.basename(f))[0]
            if stem in stems and stems[stem] != f:
                P.append(f"shots[{i}]: file name '{stem}' used by two different clips ({stems[stem]}, {f})")
            stems[stem] = f
            if not os.path.exists(f):
                P.append(f"shots[{i}]: clip missing {f}"); continue
            if f not in cache: cache[f] = probe(f)
            pr = cache[f]
            if not pr or not pr[1] or pr[0] <= 0:
                P.append(f"shots[{i}]: clip does not decode as video {f}"); continue
            st = float(c.get("start", 0) or 0)
            if st < 0: P.append(f"shots[{i}]: start {st} < 0 ({f})")
            elif slot and st + slot > pr[0] + 0.05:  # HyperFrames would freeze on the last frame
                P.append(f"shots[{i}]: {os.path.basename(f)} is {pr[0]:.2f} s but needs start {st:.2f} + {slot:.2f} s"
                         f" - use start <= {max(0, pr[0] - slot):.2f} or another clip")
    m = job.get("music")
    if m:
        mf = ap(m)
        if not os.path.exists(mf): P.append(f"music: missing {mf}")
        else:
            pr = probe(mf)
            if not pr or not pr[2] or pr[0] <= 0: P.append(f"music: does not decode as audio {mf}")
            elif float(job.get("music_start", 0)) >= pr[0]:
                P.append(f"music_start {job.get('music_start')} s >= track length {pr[0]:.1f} s")
    card = job.get("card")
    if card:
        li = card.get("line") if isinstance(card, dict) else None
        if not isinstance(li, int) or not 0 <= li < max(len(timing), 1):
            P.append(f"card.line {li!r} out of range 0..{len(timing) - 1}")
        elif "big" not in card or "word" not in card:
            P.append("card: needs 'word' and 'big'")
        elif timing:
            key = re.sub(r"[^a-z0-9]", "", str(card["word"]).lower())
            if not any(re.sub(r"[^a-z0-9]", "", w.lower()).startswith(key) for w in timing[li]["text"].split()) or not key:
                P.append(f"card.word {card['word']!r} not found in line {li}: {timing[li]['text']!r}")
    words = [re.sub(r"[^a-z0-9]", "", w.lower()) for ln in timing for w in ln.get("text", "").split()]
    for p in job.get("punch", []) or []:
        k = re.sub(r"[^a-z0-9]", "", str(p).lower())
        if not k or not any(w.startswith(k) for w in words): P.append(f"punch {p!r} matches no script word")
    od = os.path.dirname(ap(job["out"])) or "."
    if not os.path.isdir(od): P.append(f"out: folder {od} does not exist")
    for w in W: print("WARN:", w)
    if P:
        print("PREFLIGHT_FAIL\n" + "\n".join("- " + p for p in P)); sys.exit(1)
    print(f"PREFLIGHT_OK {len(timing)} lines, {sum(len(l) for l in shots)} shots, {total:.2f} s")


if __name__ == "__main__":
    main()
