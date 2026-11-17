#!/usr/bin/env python3
"""Realistic smoke test used near the end of the session.

Puts *all* example patches into one temporary directory but reconstructs only a
handful of original source files (from the first patch's pre-images), then runs
``apply_patches.py`` with no flags.  This exercises the "skip files that don't
exist" rule, hunk mismatches against a different pre-image, the collision
layout, and the exit-status policy all at once.

Usage::

    python3 tools/demo_mixed_patches.py
    python3 tools/demo_mixed_patches.py --files infer.py json2md.py
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOLS))

import apply_patches as ap  # noqa: E402
from reconstruct_preimages import reconstruct  # noqa: E402

SCRIPT = ROOT / "apply_patches.py"
DEFAULT_FILES = ["archive_converter.py", "json2md.py", "infer.py", "xztool.py"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch-dir", default=str(ROOT), help="directory with patch files")
    parser.add_argument("--files", nargs="+", default=DEFAULT_FILES,
                        help="source files to reconstruct")
    parser.add_argument("--keep", action="store_true", help="print and keep temp dir path")
    args = parser.parse_args(argv)

    patch_dir = Path(args.patch_dir)
    patches = sorted(patch_dir.glob("*.patch")) + sorted(patch_dir.glob("*.diff"))
    if not patches:
        print(f"no patch files found in {patch_dir}", file=sys.stderr)
        return 2

    diffs, _ = ap.parse_patch(ap.read_text(patches[0]))
    wanted = set(args.files)
    pre = {rel: text for rel, text in reconstruct(diffs).items() if rel in wanted}
    missing = wanted - set(pre)
    if missing:
        print(f"files not present in {patches[0].name}: {', '.join(sorted(missing))}",
              file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="patch-demo-") as tmp:
        root = Path(tmp)
        for rel, content in pre.items():
            (root / rel).write_bytes(content.encode(ap.ENCODING, ap.ERRORS))
        for patch in patches:
            shutil.copy(patch, root / patch.name)

        run = subprocess.run([sys.executable, str(SCRIPT)], cwd=root,
                             capture_output=True, text=True)
        print(f"$ python apply_patches.py   (in {root})")
        print(f"exit: {run.returncode}")
        print(run.stdout.strip())
        if run.stderr.strip():
            print("stderr (first lines):")
            print("\n".join(run.stderr.splitlines()[:5]))

        out = root / "output"
        written = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
        print(f"\noutput files ({len(written)}):")
        for rel in written[:10]:
            print(f"  {rel}")
        if len(written) > 10:
            print(f"  ... and {len(written) - 10} more")
        return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
