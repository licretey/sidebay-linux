#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
PYTHONPATH="$(pwd)" exec python3 -m sidebay "$@"
