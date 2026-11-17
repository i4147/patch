# apply_patches.py

Apply the `.patch` files in a directory to the source files they refer to and
save the patched results in an output directory.

The script implements its own unified-diff parser and applier, so it needs
**no external programs, no git repository, and no third-party packages** — just
Python 3.10+. It understands the git-style diffs used by the examples in this
repository (`diff --git`, `index`, `--- a/…` / `+++ b/…`, `@@` hunks), plus
plain multi-file unified diffs, mail headers, quoted paths, CRLF files, and
`\ No newline at end of file` markers.

## Quick start

Put the patch files and the original `.py` files together in the current
working directory, then run:

```sh
python apply_patches.py
```

That is the whole default workflow, matching `prompt.md`:

| | default |
|---|---|
| patch files | `*.patch` and `*.diff` in `.` |
| source files | `.` (paths taken from the patch) |
| results | `./output/<path>` |
| missing source files | skipped (not created, not an error) |
| `--- /dev/null` sections | skipped (use `--new-files create` to create them) |

`output/` is already listed in `.gitignore`, so results are not committed.

## Examples

```sh
# show exactly what happens to each file section
python apply_patches.py --verbose

# also create files added by "new file mode" sections
python apply_patches.py --new-files create

# keep one independent result tree per patch (no overwriting)
python apply_patches.py --layout by-patch

# patch files may also be named directly (shell globs work too)
python apply_patches.py *.patch

# custom locations / a single patch / a fresh output directory
python apply_patches.py --patch-dir patches --source-dir src \
                        --output-dir results --patches 'fix-*.patch' --clean

# validate patches without writing anything
python apply_patches.py --dry-run --strict
```

## Options

| flag | meaning |
|---|---|
| `PATCH ...` | optional explicit patch file(s), e.g. `*.patch` |
| `--patches GLOB` | patch file glob, repeatable (default `*.patch`, `*.diff`) |
| `--patch-dir DIR` | where to look for patch files (default `.`) |
| `--source-dir DIR` | where to look for the original files (default `.`) |
| `--output-dir DIR` | result directory (default `output`) |
| `--layout auto\|flat\|by-patch` | result paths, see below (default `auto`) |
| `--new-files skip\|create` | handle `--- /dev/null` sections (default `skip`) |
| `--max-offset N` | max line offset when locating a hunk (`0` = whole file) |
| `--ignore-whitespace` | match context ignoring surrounding whitespace |
| `--clean` | empty the output directory first |
| `--dry-run` | parse and apply in memory, write nothing |
| `--strict` | exit 1 if any section fails (default: report and exit 0) |
| `--verbose` / `--quiet` | per-file log / suppress the summary |

## Behaviour details

* **Skipping.** A section is skipped when the file named on its `---` side does
  not exist in the source directory. Missing files never abort the run and are
  counted in the summary (`skipped missing: N`). Binary patches, renames/copies
  without content hunks, and unsafe paths (`..`, absolute paths) are skipped
  too; `+++ /dev/null` removes the corresponding output file.
* **Multiple patches, one file.** Patches are processed in sorted filename
  order. With `--layout flat` (and `auto`), `output/<path>` holds the result of
  the last successfully applied patch. With the default `auto` layout, paths
  touched by more than one patch are *also* copied to
  `output/<patch-name>/<path>`, so no variant is silently lost. `--layout
  by-patch` writes only those per-patch trees.
* **Matching.** Hunk context is matched exactly, with a line-offset search
  (like `git apply`), so patches still apply when a file has extra lines above
  a hunk. `--ignore-whitespace` relaxes context matching. A hunk that cannot
  be matched is reported on stderr and counted as a failure; the original file
  is left out of the output rather than written back half-patched.
* **Fidelity.** Text is read/written as UTF-8 with `surrogateescape`, line
  endings (LF/CRLF), missing final newlines, unicode, and file modes are
  preserved. Blank context lines and deletion lines that look like diff
  headers (`--- …`) are handled correctly.
* **Exit codes.** `0` = run completed (including skipped/failed sections),
  `1` = failures with `--strict`, `2` = bad arguments, unreadable input, or no
  patch files found.

## Helper scripts

The scratch analysis/verification scripts used while developing this tool live
in [`tools/`](tools/HELPERS.md) (patch inspection, pre-image reconstruction,
`git apply` comparison, mixed-patch demo). Run them all with:

```sh
bash tools/check.sh
```

## Tests

```sh
python -m unittest discover -s tests -v
```

The suite covers git-style and plain unified diffs, missing files, new/deleted/
binary/mode-only sections, quoted and nested paths, offsets, CRLF, unicode,
no-newline markers, all CLI layouts, and a byte-for-byte comparison against
`git apply` for **all 543 file sections / 3,469 hunks** in the example patches
(the original `.py` files are not in this repo, so the tests reconstruct their
pre-images from the hunk context and removal lines).
