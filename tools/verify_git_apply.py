#!/usr/bin/env python3
"""Differential test: apply_patches.py vs git apply on the example patches.

For each patch file, reconstruct the original files from the hunk pre-images
(see reconstruct_preimages.py), apply the patch with ``git apply -p1`` in one
temp tree and with ``apply_patches.py`` in another, then compare every resulting
file byte-for-byte.  This is the verification harness used during the session;
the same check also lives in ``tests/test_apply_patches.py``.

Usage::

    python3 tools/verify_git_apply.py
    python3 tools/verify_git_apply.py --patch one.patch --verbose
"""

from __future__ import annotations

import argparse
import difflib
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


def verify_patch(patch: Path, *, verbose: bool = False) -> tuple[bool, str]:
    diffs, _ = ap.parse_patch(ap.read_text(patch))
    pre = reconstruct(diffs)
    with tempfile.TemporaryDirectory(prefix="patch-verify-") as tmp:
        root = Path(tmp)
        reference, mine = root / "reference", root / "mine"
        reference.mkdir()
        mine.mkdir()
        for base in (reference, mine):
            for rel, content in pre.items():
                target = base / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content.encode(ap.ENCODING, ap.ERRORS))

        git = subprocess.run(["git", "apply", "-p1", str(patch)],
                             cwd=reference, capture_output=True, text=True)
        if git.returncode != 0:
            return False, f"git apply failed: {git.stderr.strip()[:400]}"

        run = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--patch-dir", str(patch.parent), "--patches", patch.name,
             "--source-dir", str(mine), "--output-dir", str(mine / "output"),
             "--new-files", "create", "--layout", "flat", "--clean"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if run.returncode != 0:
            return False, f"apply_patches.py exited {run.returncode}: {run.stderr.strip()[:400]}"

        expected = {d.target for d in diffs if d.target and not d.is_deleted}
        got = {str(p.relative_to(mine / "output"))
               for p in (mine / "output").rglob("*") if p.is_file()}
        missing, extra = sorted(expected - got), sorted(got - expected)
        mismatched = sorted(
            rel for rel in expected & got
            if (mine / "output" / rel).read_bytes() != (reference / rel).read_bytes()
        )
        message = (f"{len(pre)} pre-images, {len(expected)} results | "
                   f"missing={len(missing)} extra={len(extra)} "
                   f"content-mismatch={len(mismatched)}")
        if verbose and (missing or extra or mismatched):
            message += f"\n  missing={missing[:3]} extra={extra[:3]} mismatch={mismatched[:3]}"
            if mismatched:
                left = (reference / mismatched[0]).read_bytes().decode(errors="replace").splitlines()
                right = (mine / "output" / mismatched[0]).read_bytes().decode(errors="replace").splitlines()
                message += "\n" + "\n".join(
                    list(difflib.unified_diff(left, right, "git apply", "apply_patches.py", n=1))[:20]
                )
        return not (missing or extra or mismatched), message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch-dir", default=str(ROOT), help="directory with patch files")
    parser.add_argument("--patch", action="append", default=None,
                        help="patch file name or glob, repeatable (default: all)")
    parser.add_argument("--verbose", action="store_true", help="show diffs on mismatch")
    args = parser.parse_args(argv)

    if shutil.which("git") is None:
        print("git is not installed; skipping comparison", file=sys.stderr)
        return 2

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

    failures = 0
    for patch in sorted(patches, key=lambda p: p.name):
        ok, message = verify_patch(patch, verbose=args.verbose)
        print(f"{'OK  ' if ok else 'FAIL'} {patch.name}: {message}")
        failures += 0 if ok else 1
    print(f"{len(patches)} patch(es) checked, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
