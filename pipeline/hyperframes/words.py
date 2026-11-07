"""Exact word timestamps per tts line via faster-whisper, mapped onto the script words.
Usage: python3 words.py vo_dir  -> writes vo_dir/words.json [[{"w","s","e"}...] per line]"""
import json, os, re, sys
from faster_whisper import WhisperModel
import numpy as np, scipy.io.wavfile as wavf
from scipy.signal import resample_poly
def load(p):
    sr, a = wavf.read(p); a = a.astype(np.float32) / 32768
    return resample_poly(a, 2, 3).astype(np.float32) if sr == 24000 else a
if len(sys.argv) < 2: sys.exit(__doc__)
vo = sys.argv[1]; timing = json.load(open(os.path.join(vo, "timing.json")))
for ln in timing:  # timing.json from older tts.py stores paths relative to the tts cwd
    if not os.path.exists(ln["file"]): ln["file"] = os.path.join(vo, os.path.basename(ln["file"]))
m = WhisperModel("base.en", device="cpu", compute_type="int8")
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
out = []
for ln in timing:
    script = ln["text"].split()
    segs, _ = m.transcribe(load(ln["file"]), word_timestamps=True, beam_size=5, condition_on_previous_text=False, initial_prompt=ln["text"])
    hw = []
    for w in (w for s in segs for w in (s.words or [])):
        if hw and w.word and not w.word[0].isspace() and not w.word.strip()[:1].isalpha():
            hw[-1] = type("W", (), {"word": hw[-1].word + w.word, "start": hw[-1].start, "end": w.end})  # "$69" + ".99"
        else:
            hw.append(w)
    res = []
    n = len(script)
    if len(hw) > n and sum(norm(a.word) == norm(b) for a, b in zip(hw, script)) >= 0.7 * n:
        hw = hw[:n]  # whisper repeated itself after the real speech - keep the matching prefix
    if len(hw) == n:
        res = [{"w": sw, "s": h.start, "e": h.end} for sw, h in zip(script, hw)]
    else:  # align by characters: spread whisper's total speech span over script words
        a = hw[0].start if hw else 0.0; b = hw[-1].end if hw else ln["dur"]
        tot = sum(len(norm(w)) or 1 for w in script); t = a
        for sw in script:
            d = (b - a) * (len(norm(sw)) or 1) / tot; res.append({"w": sw, "s": t, "e": t + d}); t += d
        print("  fallback line:", ln["text"], "| heard:", " ".join(h.word for h in hw))
    # whisper base drifts ~0.2 s: stretch its span onto the real speech span (energy gate, -40 dB)
    a16 = load(ln["file"]); fr = 160; env = np.array([np.sqrt(np.mean(a16[i:i+fr]**2)) for i in range(0, len(a16) - fr, fr)])
    on = np.where(env > 10 ** (-40 / 20))[0]
    if len(on) and res:
        s0, s1 = on[0] * 0.01, (on[-1] + 1) * 0.01; w0, w1 = res[0]["s"], res[-1]["e"]
        k = (s1 - s0) / max(w1 - w0, 1e-3)
        for r in res: r["s"] = round(s0 + (r["s"] - w0) * k, 3); r["e"] = round(s0 + (r["e"] - w0) * k, 3)
    prev = 0.0  # keep times monotonic and inside the line (whisper can return overlapping/zero-length words)
    for r in res:
        r["s"] = round(min(max(r["s"], prev), ln["dur"] - 0.05), 3); r["e"] = round(min(max(r["e"], r["s"] + 0.05), ln["dur"]), 3); prev = r["s"]
    if len(res) != len(script): sys.exit(f"WORDS FAIL: line {ln['text']!r}: {len(res)} timings for {len(script)} words")
    out.append(res)
    print(" ".join(f"{r['w']}@{r['s']:.2f}" for r in res))
json.dump(out, open(os.path.join(vo, "words.json"), "w"), indent=1)
print("WORDS_OK", len(out), "lines")
