#!/usr/bin/env python3
"""Rebuild approximate original source files from a patch's pre-image lines.

The example patches were generated against `.py` files that are not checked
into this repository.  Every hunk's context and removal lines give us the
original lines at their exact line numbers; gaps between hunks are filled with
unique ``FILLER_<n>`` lines so hunk offsets still line up.  The reconstructed
files are good enough to apply the patch and to compare against ``git apply``.

Usage::

    python3 tools/reconstruct_preimages.py --out-dir /tmp/sources --clean
    python3 tools/reconstruct_preimages.py --patch one.patch --out-dir /tmp/sources

Importable::

    from reconstruct_preimages import reconstruct
    files = reconstruct(diffs)   # {relative path: file text}
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import apply_patches as ap  # noqa: E402


def reconstruct(diffs) -> dict[str, str]:
    """Return ``{old_path: file_text}`` for every section with an old file."""
    files: dict[str, str] = {}
    for diff in diffs:
        if diff.old_path is None or not diff.hunks:
            continue
        placed: dict[int, str] = {}
        for hunk in diff.hunks:
            for offset, line in enumerate(hunk.old_lines):
                index = hunk.anchor + offset
                text = line.text + "\n"
                if index in placed and placed[index] != text:
                    raise ValueError(
                        f"conflicting pre-image lines in {diff.old_path} at line {index + 1}"
                    )
                placed[index] = text
        if not placed:
            files[diff.old_path] = ""
            continue
        size = max(placed) + 1
        files[diff.old_path] = "".join(
            placed.get(index, f"FILLER_{index}\n") for index in range(size)
        )
    return files


def write_tree(files: dict[str, str], out_dir: Path, clean: bool = False) -> int:
    if clean and out_dir.exists():
        if out_dir.is_dir():
            shutil.rmtree(out_dir)
        else:
            out_dir.unlink()
    for rel, content in files.items():
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode(ap.ENCODING, ap.ERRORS))
    return len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch-dir", default=str(ROOT), help="directory with patch files")
    parser.add_argument("--patch", action="append", default=None,
                        help="patch file name or glob, repeatable (default: all)")
    parser.add_argument("--out-dir", required=True, help="where to write reconstructed files")
    parser.add_argument("--clean", action="store_true", help="empty out-dir first")
    args = parser.parse_args(argv)

    patch_dir = Path(args.patch_dir)
    patterns = args.patch or ["*.patch", "*.diff"]
    patches: set[Path] = set()
    for pattern in patterns:
        direct = patch_dir / pattern
        if direct.is_file():
            patches.add(direct)
        else:
            patches.update(p for p in patch_dir.glob(pattern) if p.is_file())
    if not patches:
        print(f"no patch files found in {patch_dir}", file=sys.stderr)
        return 2

    files: dict[str, str] = {}
    for patch in sorted(patches, key=lambda p: p.name):
        diffs, _ = ap.parse_patch(ap.read_text(patch))
        reconstructed = reconstruct(diffs)
        for rel, content in reconstructed.items():
            # Later patches may describe a different version of the same file;
            # keep the first one, which is what a single source tree would hold.
            files.setdefault(rel, content)
        print(f"{patch.name}: {len(reconstructed)} pre-image file(s)")
    count = write_tree(files, Path(args.out_dir), args.clean)
    print(f"wrote {count} file(s) to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
