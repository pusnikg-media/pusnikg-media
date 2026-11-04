"""Exact word timestamps per tts line via faster-whisper, mapped onto the script words.
Usage: python3 words.py vo_dir  -> writes vo_dir/words.json [[{"w","s","e"}...] per line]"""
import json, os, re, sys
from faster_whisper import WhisperModel
import numpy as np, scipy.io.wavfile as wavf
from scipy.signal import resample_poly
def load(p):
    sr, a = wavf.read(p); a = a.astype(np.float32) / 32768
    return resample_poly(a, 2, 3).astype(np.float32) if sr == 24000 else a
vo = sys.argv[1]; timing = json.load(open(os.path.join(vo, "timing.json")))
m = WhisperModel("base.en", device="cpu", compute_type="int8")
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
out = []
for ln in timing:
    script = ln["text"].split()
    segs, _ = m.transcribe(load(ln["file"]), word_timestamps=True, beam_size=5, condition_on_previous_text=False, initial_prompt=ln["text"])
    hw = [w for s in segs for w in s.words]
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
    out.append(res)
    print(" ".join(f"{r['w']}@{r['s']:.2f}" for r in res))
json.dump(out, open(os.path.join(vo, "words.json"), "w"), indent=1)
