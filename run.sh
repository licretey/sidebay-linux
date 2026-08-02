#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ] || ! grep -q '^include-system-site-packages = true' .venv/pyvenv.cfg 2>/dev/null; then
  echo "First run: creating uv environment (system-site-packages)..." >&2
  rm -rf .venv
  uv venv --system-site-packages
  uv sync
fi
exec uv run --no-sync sidebay "$@"
