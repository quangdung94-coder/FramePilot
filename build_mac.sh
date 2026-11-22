#!/usr/bin/env bash
# build_mac.sh - Đóng gói bản SẠCH FramePilot cho macOS Apple Silicon (arm64)
# Cách chạy trên Mac chip M (hoặc GitHub Actions macos-14):
#   chmod +x build_mac.sh && ./build_mac.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
python3 "$ROOT/build_mac.py" "$@"
