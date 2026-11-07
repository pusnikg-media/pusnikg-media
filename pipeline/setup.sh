#!/usr/bin/env bash
# One-time setup per fresh session (~1-2 min). Only standard package installs + model data files:
#   espeak-ng from the Ubuntu package archive (apt), faster-whisper from PyPI (pip),
#   Kokoro ONNX model + voices as data files (no code) from the kokoro-onnx GitHub release.
# v2 (07.11.): no more cloning/compiling espeak-ng from source - scheduled runs block "code from external".
set -e
mkdir -p /home/claude/tts && cd /home/claude/tts
if ! command -v espeak-ng >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get install -y -q espeak-ng >/dev/null 2>&1 || { apt-get update -q >/dev/null && apt-get install -y -q espeak-ng >/dev/null; }
fi
B=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
[ -s voices-v1.0.bin ] || curl -sSL -o voices-v1.0.bin $B/voices-v1.0.bin
[ -s kokoro-v1.0.onnx ] || curl -sSL -o kokoro-v1.0.onnx $B/kokoro-v1.0.onnx
python3 -c "import faster_whisper" 2>/dev/null || pip install -q --break-system-packages faster-whisper
python3 -c "import onnxruntime, numpy, scipy, PIL, faster_whisper" && espeak-ng --version && echo SETUP_OK
