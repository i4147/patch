# Session helper scripts

Scratch tools used while building `apply_patches.py` in this session. They are
kept here so the analysis and verification steps are reproducible. All of them
resolve paths relative to the repository root, so they can be run from any
working directory. Requirements: Python 3.10+; `git` only for
`verify_git_apply.py`.

> This file is called `HELPERS.md`, not `README.md`: `tools/README.md` is a path
> that the example patches modify, and adding a file there would make a plain
> `python apply_patches.py` run try (and fail) to patch it. None of the helper
> filenames appear in any patch target.

| helper | what it was used for | run it with |
|---|---|---|
| `inspect_patches.sh` | first shell-level look at the example patches: sizes, section/hunk counts, `/dev/null` sections, target paths, hunk header variants | `bash tools/inspect_patches.sh` |
| `inspect_patches.py` | structured Python analysis: per-patch stats, target paths touched by several patches, `index` blob transitions, CRLF / non-ASCII checks | `python3 tools/inspect_patches.py [--json]` |
| `reconstruct_preimages.py` | rebuild approximate original `.py` files from hunk context/removal lines (gaps filled with `FILLER_<n>`), since the sources are not checked in | `python3 tools/reconstruct_preimages.py --out-dir /tmp/preimages` |
| `verify_git_apply.py` | compare `apply_patches.py` byte-for-byte against `git apply` on every file section of the example patches | `python3 tools/verify_git_apply.py` |
| `demo_mixed_patches.py` | realistic smoke test: all example patches in one directory but only a handful of source files, exercising skip / collision / mismatch reporting | `python3 tools/demo_mixed_patches.py` |
| `check.sh` | one-shot run of the unit tests, the `git apply` comparison and the default CLI | `bash tools/check.sh` |

Examples:

```sh
# quick look at one patch only
bash tools/inspect_patches.sh 01a1d19f-5be3-70c7-b5f7-46c30a5460d1.patch

# machine-readable report
python3 tools/inspect_patches.py --json > /tmp/patch-report.json

# rebuild sources for just one patch, then apply it with the main script
python3 tools/reconstruct_preimages.py \
    --patch 01a1d19f-5be3-70c7-b5f7-46c30a5460d1.patch \
    --out-dir /tmp/sources --clean
python3 apply_patches.py --patch-dir . --source-dir /tmp/sources \
    --output-dir /tmp/results --patches 01a1d19f-5be3-70c7-b5f7-46c30a5460d1.patch
```

`reconstruct_preimages.py` is also importable (`from reconstruct_preimages
import reconstruct`) and is shared by `verify_git_apply.py` and
`demo_mixed_patches.py`.

The publishing commands used for the pull request were plain `git` / `gh`:

```sh
git add <files> && git commit -m "..."
git push origin arena/bed4074a-patch
gh pr create --base main --head arena/bed4074a-patch --body-file <body>
```
