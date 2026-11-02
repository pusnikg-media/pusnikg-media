"""Royalty-free synthwave bed, generated from scratch. Usage: music.py seconds out.wav [seed]"""
import sys, numpy as np, scipy.io.wavfile as wav
from scipy.signal import butter, lfilter
SR = 44100
dur = float(sys.argv[1]); out = sys.argv[2]; seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
rng = np.random.default_rng(seed)
bpm = 100; beat = 60 / bpm; bar = 4 * beat
N = int(SR * (dur + 1)); t = np.arange(N) / SR
mix = np.zeros(N)
def lp(x, f): b, a = butter(2, f / (SR / 2)); return lfilter(b, a, x)
def hp(x, f): b, a = butter(2, f / (SR / 2), "high"); return lfilter(b, a, x)
def note(m): return 440 * 2 ** ((m - 69) / 12)
progs = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
progs = progs[seed % 4:] + progs[:seed % 4]
def saw(f, tt): return sum(np.sin(2 * np.pi * f * k * tt) / k for k in range(1, 8))
# pad
pad = np.zeros(N)
nb = int(np.ceil(dur / bar)) + 1
for b in range(nb):
    s = int(b * bar * SR); e = min(N, int((b + 1) * bar * SR))
    if s >= N: break
    tt = t[s:e] - t[s]
    env = np.minimum(1, tt / 0.4) * np.minimum(1, (bar - tt) / 0.3)
    for m in progs[b % 4]:
        for det in (-0.08, 0.08):
            pad[s:e] += saw(note(m) * (1 + det / 100), tt) * env
mix += lp(pad, 1800) * 0.05
# bass eighths
for i in range(int(dur / (beat / 2)) + 2):
    s = int(i * beat / 2 * SR); L = int(beat / 2 * SR * 0.9); e = min(N, s + L)
    if s >= N: break
    tt = t[s:e] - t[s]; root = progs[int(i * beat / 2 // bar) % 4][0] - 24
    mix[s:e] += lp(saw(note(root), tt), 600) * np.exp(-tt * 6) * 0.22
# drums
for i in range(int(dur / beat) + 2):
    s = int(i * beat * SR)
    if s >= N: break
    L = min(N - s, int(0.35 * SR)); tt = t[:L]
    f = 45 + 80 * np.exp(-tt * 30)
    mix[s:s + L] += np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9) * 0.55
    if i % 2 == 1:
        L2 = min(N - s, int(0.2 * SR)); tt2 = t[:L2]
        mix[s:s + L2] += hp(rng.standard_normal(L2), 1500) * np.exp(-tt2 * 18) * 0.16
    for h in (0, 0.5):
        hs = int((i + h) * beat * SR); L3 = min(N - hs, int(0.05 * SR))
        if L3 > 0: mix[hs:hs + L3] += hp(rng.standard_normal(L3), 7000) * np.exp(-t[:L3] * 70) * 0.05
mix = mix[:int(dur * SR)]
fade = int(1.5 * SR); mix[-fade:] *= np.linspace(1, 0, fade); mix[:int(0.05*SR)] *= np.linspace(0, 1, int(0.05*SR))
mix /= np.max(np.abs(mix)) * 1.12
st = np.stack([mix, np.roll(mix, 300)], 1)
wav.write(out, SR, (st * 32767).astype(np.int16))
