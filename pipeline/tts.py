"""Kokoro TTS (ONNX) with espeak-ng CLI phonemizer. No PyPI needed.
Usage: python3 tts.py script.txt out_dir [voice] [speed]
script.txt: one sentence per line. Writes out_dir/line_XX.wav (24 kHz) + timing.json"""
import json, re, subprocess, sys, os
import numpy as np, onnxruntime as ort, scipy.io.wavfile as wav

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("KOKORO_DIR", "/home/claude/tts")
VOCAB = json.load(open(os.path.join(HERE, "kokoro_config.json")))["vocab"]
PUNCT = ';:,.!?¡¿—…"«»“”'

def espeak(chunk):
    out = subprocess.run(["espeak-ng", "-q", "--ipa", "-v", "en-us"], input=chunk,
                         capture_output=True, text=True).stdout
    return " ".join(out.split())

ROMAN = {"II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6"}


def normalize(text):
    """Spoken form for espeak only (captions keep the script text). Fixes: '$69.99' was read
    'dollar sixty-nine. ninety-nine' (split on the decimal point), '$70' -> 'dollar seventy',
    'GTA VI' -> 'G-T-A V-I', '1,000' -> 'one, zero zero zero'."""
    text = text.replace("’", "'").replace("‘", "'").strip()
    text = re.sub(r"\b(GTA|Grand Theft Auto)\s+(VI|V|IV|III|II)\b", lambda m: m.group(1) + " " + ROMAN[m.group(2)], text)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # 1,000 -> 1000
    text = re.sub(r"\bvs\.?(?=\s)", "versus", text, flags=re.I)
    text = re.sub(r"\$(\d+)\.(\d\d)\b", r"\1 dollars \2", text)  # $69.99 -> 69 dollars 99
    text = re.sub(r"\$(\d+(?:\.\d+)?)(\s*(?:million|billion|thousand|k)\b)?",
                  lambda m: m.group(1) + (m.group(2) or "") + " dollars", text)  # $70 -> 70 dollars
    return text


def phonemize(text):
    text = normalize(text)
    # punctuation splits the text for espeak; a '.' or ',' between digits (2.5, 1,5) is not punctuation
    parts = re.split(r'((?:[;:!?—…"“”]|(?<!\d)[.,]|[.,](?!\d))+)', text)
    ps = ""
    for p in parts:
        if not p.strip():
            continue
        if re.fullmatch(r'[;:,.!?—…"“”]+', p.strip()):
            ps = ps.rstrip() + p + " "
        else:
            ps += espeak(p) + " "
    ps = ps.replace("ʲ", "j").replace("r", "ɹ").replace("x", "k").replace("ɬ", "l")
    ps = re.sub(r"(?<=[a-zɹː])(?=hˈʌndɹɪd)", " ", ps)
    ps = re.sub(r' z(?=[;:,.!?¡¿—…"«»“” ]|$)', "z", ps)
    ps = re.sub(r"(?<=nˈaɪn)ti(?!ː)", "di", ps)
    return "".join(c for c in ps if c in VOCAB).strip()

def main():
    src, out = sys.argv[1], sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else "am_puck"
    speed = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    os.makedirs(out, exist_ok=True)
    for f in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        if not os.path.exists(os.path.join(MODELS, f)):
            sys.exit(f"TTS FAIL: {MODELS}/{f} missing - run: bash pipeline/setup.sh")
    if os.path.exists(os.path.join(out, "words.json")):
        os.remove(os.path.join(out, "words.json"))  # stale word timings from an older script would be reused by render_hf
    for f in os.listdir(out):
        if re.fullmatch(r"line_\d+\.wav", f):
            os.remove(os.path.join(out, f))  # leftovers from a longer old script
    sess = ort.InferenceSession(os.path.join(MODELS, "kokoro-v1.0.onnx"), providers=["CPUExecutionProvider"])
    names = {i.name: i for i in sess.get_inputs()}
    tok_name = "input_ids" if "input_ids" in names else "tokens"
    voices = np.load(os.path.join(MODELS, "voices-v1.0.bin"))
    if voice not in voices.files:
        sys.exit(f"TTS FAIL: voice '{voice}' unknown")
    styles = voices[voice]
    lines = [l.strip() for l in open(src, encoding="utf-8") if l.strip()]
    if not lines:
        sys.exit(f"TTS FAIL: {src} has no text lines")
    timing = []
    for i, line in enumerate(lines):
        ps = phonemize(line)
        toks = [VOCAB[c] for c in ps]
        if not toks or len(toks) >= len(styles) - 1:
            sys.exit(f"TTS FAIL line {i}: {len(toks)} phoneme tokens (need 1..{len(styles) - 2}) - split or fix the line: {line!r}")
        style = styles[len(toks)]  # (1,256)
        audio = sess.run(None, {tok_name: np.array([[0, *toks, 0]], dtype=np.int64),
                                "style": style.astype(np.float32),
                                "speed": np.array([speed], dtype=np.float32)})[0].squeeze()
        f = os.path.join(out, f"line_{i:02d}.wav")
        wav.write(f, 24000, (np.clip(audio, -1, 1) * 32767).astype(np.int16))
        if len(audio) < 2400 or not np.isfinite(audio).all() or np.abs(audio).max() < 1e-3:
            sys.exit(f"TTS FAIL line {i}: empty/silent audio for {line!r}")
        timing.append({"text": line, "file": os.path.abspath(f), "dur": len(audio) / 24000, "phonemes": ps})
        print(f"{i}: {len(audio)/24000:.2f}s  {ps}")
    json.dump(timing, open(os.path.join(out, "timing.json"), "w"), indent=1, ensure_ascii=False)
    print(f"TTS_OK {len(timing)} lines {sum(t['dur'] for t in timing):.2f}s")

if __name__ == "__main__":
    main()
