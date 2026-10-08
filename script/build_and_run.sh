#!/usr/bin/env bash
set -euo pipefail
WIXAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WIXAL_ROOT"
if [[ "${1:-run}" == "--package-only" ]]; then
  exec "$WIXAL_ROOT/native/.venv/bin/python" native/scripts/package.py --alpha
fi
pkill -x WixalNative >/dev/null 2>&1 || true
"$WIXAL_ROOT/native/.venv/bin/python" native/scripts/package.py --alpha
WIXAL_BUNDLE="$WIXAL_ROOT/release/native/Wixal.app"
WIXAL_LAUNCH_ENV=()
for WIXAL_LAUNCH_KEY in WIXAL_NATIVE_DATA WIXAL_NATIVE_ACCEPTANCE WIXAL_NATIVE_ENDPOINT; do
  if [[ -n "${!WIXAL_LAUNCH_KEY:-}" ]]; then WIXAL_LAUNCH_ENV+=(--env "$WIXAL_LAUNCH_KEY=${!WIXAL_LAUNCH_KEY}"); fi
done
open -n "$WIXAL_BUNDLE" "${WIXAL_LAUNCH_ENV[@]}"
case "${1:-run}" in
  run) ;;
  --verify) sleep 2; pgrep -x WixalNative >/dev/null ;;
  --debug) sleep 2; lldb -n WixalNative ;;
  --logs|--telemetry) /usr/bin/log stream --info --style compact --predicate 'process == "WixalNative"' ;;
  *) echo "Usage: $0 [--package-only|--verify|--debug|--logs|--telemetry]" >&2; exit 2 ;;
esac
