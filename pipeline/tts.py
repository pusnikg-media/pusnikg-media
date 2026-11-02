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

def phonemize(text):
    text = text.replace("’", "'").strip()
    parts = re.split(r'([;:,.!?—…"“”]+)', text)
    ps = ""
    for p in parts:
        if not p.strip():
            continue
        if re.fullmatch(r'[;:,.!?—…"“”]+', p):
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
    sess = ort.InferenceSession(os.path.join(MODELS, "kokoro-v1.0.onnx"), providers=["CPUExecutionProvider"])
    names = {i.name: i for i in sess.get_inputs()}
    tok_name = "input_ids" if "input_ids" in names else "tokens"
    styles = np.load(os.path.join(MODELS, "voices-v1.0.bin"))[voice]
    lines = [l.strip() for l in open(src) if l.strip()]
    timing = []
    for i, line in enumerate(lines):
        ps = phonemize(line)
        toks = [VOCAB[c] for c in ps]
        style = styles[len(toks)]  # (1,256)
        audio = sess.run(None, {tok_name: np.array([[0, *toks, 0]], dtype=np.int64),
                                "style": style.astype(np.float32),
                                "speed": np.array([speed], dtype=np.float32)})[0].squeeze()
        f = os.path.join(out, f"line_{i:02d}.wav")
        wav.write(f, 24000, (np.clip(audio, -1, 1) * 32767).astype(np.int16))
        timing.append({"text": line, "file": f, "dur": len(audio) / 24000, "phonemes": ps})
        print(f"{i}: {len(audio)/24000:.2f}s  {ps}")
    json.dump(timing, open(os.path.join(out, "timing.json"), "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
