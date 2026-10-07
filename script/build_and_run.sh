#!/usr/bin/env bash
set -euo pipefail
WIXAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WIXAL_ROOT"
pkill -x WixalNative >/dev/null 2>&1 || true
"$WIXAL_ROOT/native/.venv/bin/python" native/scripts/package.py --development
WIXAL_BUNDLE="$WIXAL_ROOT/release/native/Wixal Native.app"
open -n "$WIXAL_BUNDLE"
case "${1:-run}" in
  run) ;;
  --verify) sleep 2; pgrep -x WixalNative >/dev/null ;;
  --debug) sleep 2; lldb -n WixalNative ;;
  --logs|--telemetry) /usr/bin/log stream --info --style compact --predicate 'process == "WixalNative"' ;;
  *) echo "Usage: $0 [--verify|--debug|--logs|--telemetry]" >&2; exit 2 ;;
esac
