#!/usr/bin/env bash
# Install ffmpeg (+ espeak-ng with arg "espeak") on a GitHub runner WITHOUT depending on Ubuntu's apt mirrors.
# Why (11.11.2026): apt mirrors were unreachable from GitHub runners; apt-get hung until the job timeout
# (ai-assets ran into its 60-min limit twice). Now: static ffmpeg from GitHub; espeak-ng via apt with short
# timeouts, falling back to conda-forge (micromamba). Never hangs longer than ~15 min, fails loudly instead.
# Usage: bash pipeline/install_tools.sh [espeak]
set -u
NEED_ESPEAK=${1:-}
export DEBIAN_FRONTEND=noninteractive
A=(-o Acquire::Retries=2 -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 -o DPkg::Lock::Timeout=60)

if ! command -v ffmpeg >/dev/null; then
  FF=https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
  for i in 1 2 3; do
    curl -fsSL --retry 3 --max-time 300 -o /tmp/ff.tar.xz "$FF" && tar -xJf /tmp/ff.tar.xz -C "$HOME" && break
    echo "ffmpeg download retry $i"; sleep 5
  done
  sudo ln -sf "$HOME"/ffmpeg-master-latest-linux64-gpl/bin/ff* /usr/local/bin/ 2>/dev/null
fi

if [ -n "$NEED_ESPEAK" ] && ! command -v espeak-ng >/dev/null; then
  [ -n "${SKIP_APT:-}" ] || {
  timeout 120 sudo -E apt-get "${A[@]}" update -q >/dev/null 2>&1
  timeout 180 sudo -E apt-get "${A[@]}" install -y -q --no-install-recommends espeak-ng >/dev/null 2>&1
  }
  if ! command -v espeak-ng >/dev/null; then
    echo "apt failed - installing espeak-ng from conda-forge"
    MM=https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-linux-64
    curl -fsSL --retry 3 --max-time 120 -o "$HOME/micromamba" "$MM" && chmod +x "$HOME/micromamba"
    timeout 600 "$HOME/micromamba" create -y -r "$HOME/mamba" -p "$HOME/espeak" -c conda-forge espeak-ng 2>&1 | tail -15
    ls -la "$HOME/espeak/bin" 2>&1 | head -20
    E=$(ls "$HOME"/espeak/bin/espeak-ng* "$HOME"/espeak/bin/espeak 2>/dev/null | head -1)
    [ -n "$E" ] && sudo ln -sf "$E" /usr/local/bin/espeak-ng
  fi
fi

command -v ffmpeg >/dev/null || { echo "TOOLS FAIL: ffmpeg"; exit 1; }
ffmpeg -version | head -1
if [ -n "$NEED_ESPEAK" ]; then
  echo "hello world" | espeak-ng -q --ipa -v en-us || { echo "TOOLS FAIL: espeak-ng"; exit 1; }
fi
echo TOOLS_OK
