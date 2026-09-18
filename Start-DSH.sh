#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.cargo/bin:$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"
exec python3 "$ROOT/scripts/start_unix.py" "$@"
