#!/usr/bin/env bash
set -euo pipefail
umask 077
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd)"
if [[ -f "$SCRIPT_DIR/scripts/pythonanywhere_setup.py" ]]; then
    exec python3 "$SCRIPT_DIR/scripts/pythonanywhere_setup.py" "$@"
fi
BOOTSTRAP_FILE="$(mktemp "${TMPDIR:-/tmp}/kontrol-setup.XXXXXXXX.py")"
trap 'rm -f -- "$BOOTSTRAP_FILE"' EXIT
curl --fail --show-error --silent --location \
    https://raw.githubusercontent.com/seghobs/kontrolv-new/main/scripts/pythonanywhere_setup.py \
    --output "$BOOTSTRAP_FILE"
python3 "$BOOTSTRAP_FILE" "$@"
