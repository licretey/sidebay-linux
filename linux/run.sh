#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "First run: creating uv environment (system-site-packages)..." >&2
  uv venv --system-site-packages
  uv sync
fi
exec uv run --no-sync sidebay "$@"
