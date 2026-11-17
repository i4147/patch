#!/usr/bin/env bash
# Quick shell-level look at patch files (the first exploration step this session).
# Usage: bash tools/inspect_patches.sh [PATCH ...]
set -euo pipefail

cd "$(dirname "$0")/.."

patches=("$@")
if ((${#patches[@]} == 0)); then
    shopt -s nullglob
    patches=( *.patch *.diff )
fi
if ((${#patches[@]} == 0)); then
    echo "no patch files found" >&2
    exit 1
fi

count() { grep -c -- "$1" "$2" || true; }
countE() { grep -Ec -- "$1" "$2" || true; }

for f in "${patches[@]}"; do
    printf '=== %s ===\n' "$f"
    wc -l -c "$f"
    printf 'sections: %s | --- : %s | +++ : %s | hunks: %s\n' \
        "$(count '^diff --git' "$f")" \
        "$(count '^--- ' "$f")" \
        "$(count '^+++ ' "$f")" \
        "$(count '^@@ ' "$f")"
    printf '/dev/null: %s | new file mode: %s | deleted file mode: %s | binary: %s | rename/copy: %s | no-newline: %s\n' \
        "$(count '/dev/null' "$f")" \
        "$(count '^new file mode' "$f")" \
        "$(count '^deleted file mode' "$f")" \
        "$(countE '^(GIT binary patch|Binary files)' "$f")" \
        "$(countE '^(rename|copy) (from|to)' "$f")" \
        "$(count '^\\ No newline at end of file' "$f")"
    echo '-- first 12 lines --'
    head -12 "$f"
    echo
done

echo '=== most frequently patched target paths ==='
grep -h '^+++ ' "${patches[@]}" | sort | uniq -c | sort -rn | head -15 || true

echo
echo '=== target paths containing subdirectories ==='
grep -h '^+++ ' "${patches[@]}" | sed -E 's/^\+\+\+ b?\/?//' | grep '/' | sort -u | head -20 || true

echo
echo '=== hunk header variants (normalised) ==='
grep -h '^@@ ' "${patches[@]}" | sed -E 's/@@.*@@.*/@@ ... @@ tail/' | sort | uniq -c || true

echo
echo '=== section headers other than ---/+++/@@/index (sample) ==='
grep -hE '^(From |Subject:|Date:|Index:|Binary|GIT binary|rename |copy |similarity|old mode|new mode)' \
    "${patches[@]}" | sort | uniq -c | sort -rn | head -15 || true
