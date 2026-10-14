#!/bin/bash
set -eo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONUTF8=1
export FGO_CAP_METHOD="${FGO_CAP_METHOD:-ADBCAP}"
case "${1:-cli}" in
  install)
    command -v cbc >/dev/null || brew install cbc
    uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python -r requirements-headless.txt
    ;;
  check)
    shift
    exec .venv/bin/python deploy/macos_check.py "$@"
    ;;
  cli)
    shift || true
    exec .venv/bin/python FGO-py/fgo.py cli --no-color "$@"
    ;;
  *) echo 'Usage: macos.sh {install|cli|check [serial]}' >&2; exit 2 ;;
esac
