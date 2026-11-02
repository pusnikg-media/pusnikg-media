#!/usr/bin/env bash
# One-time setup per fresh session (~3 min): espeak-ng from source + Kokoro ONNX model from GitHub releases.
set -e
mkdir -p /home/claude/tts && cd /home/claude/tts
if ! command -v espeak-ng >/dev/null; then
  [ -d src-espeak ] || git clone -q --depth 1 https://github.com/espeak-ng/espeak-ng src-espeak
  cd src-espeak && cmake -B build -DCMAKE_BUILD_TYPE=Release -DUSE_MBROLA=OFF -DUSE_LIBSONIC=OFF -DUSE_LIBPCAUDIO=OFF -DUSE_ASYNC=OFF -DCMAKE_INSTALL_PREFIX=/usr/local >/dev/null \
    && cmake --build build -j8 >/dev/null && cmake --install build >/dev/null && cd ..
fi
B=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
[ -s voices-v1.0.bin ] || curl -sSL -o voices-v1.0.bin $B/voices-v1.0.bin
[ -s kokoro-v1.0.onnx ] || curl -sSL -o kokoro-v1.0.onnx $B/kokoro-v1.0.onnx
python3 -c "import onnxruntime, numpy, scipy, PIL" && espeak-ng --version && echo SETUP_OK
