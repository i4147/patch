#!/usr/bin/env bash
# One-shot verification runner: the same commands used during the session.
# Usage: bash tools/check.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo '=== unit / integration tests ==='
python3 -m unittest discover -s tests -v

echo
echo '=== byte-for-byte comparison against git apply ==='
python3 tools/verify_git_apply.py

echo
echo '=== default CLI smoke test (no source files in this repo) ==='
python3 apply_patches.py

echo
echo '=== all checks passed ==='
