#!/usr/bin/env bash
# Install ffmpeg (+ espeak-ng with arg "espeak") on a GitHub runner WITHOUT depending on Ubuntu's apt mirrors.
# Why (11.11.2026): apt mirrors were unreachable from GitHub runners; apt-get hung until the job timeout
# (ai-assets ran into its 60-min limit twice). Now: static ffmpeg from GitHub; espeak-ng via apt with short
# timeouts, falling back to independent Ubuntu mirrors. Never hangs longer than ~15 min, fails loudly instead.
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
    # runner's default mirrors (azure/security.ubuntu.com) hung on 11.11. -> try independent Ubuntu mirrors
    CS=$(. /etc/os-release && echo "$VERSION_CODENAME")
    for M in http://mirrors.kernel.org/ubuntu http://mirror.math.princeton.edu/pub/ubuntu http://ftp.uni-stuttgart.de/ubuntu http://archive.ubuntu.com/ubuntu; do
      echo "apt default mirrors failed - trying $M"
      echo "deb $M $CS main universe" | sudo tee /etc/apt/alt.list >/dev/null
      ALT=(-o Dir::Etc::sourcelist=/etc/apt/alt.list -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0)
      timeout 90 sudo -E apt-get "${A[@]}" "${ALT[@]}" update -q >/dev/null 2>&1 || continue
      timeout 150 sudo -E apt-get "${A[@]}" "${ALT[@]}" install -y -q --no-install-recommends espeak-ng >/dev/null 2>&1
      command -v espeak-ng >/dev/null && { echo "espeak-ng from $M"; break; }
    done
  fi
fi

command -v ffmpeg >/dev/null || { echo "TOOLS FAIL: ffmpeg"; exit 1; }
ffmpeg -version | head -1
if [ -n "$NEED_ESPEAK" ]; then
  echo "hello world" | espeak-ng -q --ipa -v en-us || { echo "TOOLS FAIL: espeak-ng"; exit 1; }
fi
echo TOOLS_OK
