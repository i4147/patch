#!/usr/bin/env python3
"""Structured report about the example patch files.

This is the Python half of the exploration I did at the start of the session:
section/hunk counts, new/deleted/binary sections, target paths shared by
several patches, ``index`` blob transitions, and line-ending/encoding checks.

Usage::

    python3 tools/inspect_patches.py [--patch-dir DIR] [--patches GLOB ...] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import apply_patches as ap  # noqa: E402


def inspect(path: Path) -> dict:
    raw = path.read_bytes()
    text = raw.decode(ap.ENCODING, ap.ERRORS)
    lines, patch_eol = ap.split_patch_lines(text)
    diffs, _ = ap.parse_patch(text)

    index_lines: dict[str, list[str]] = defaultdict(list)
    for diff in diffs:
        for header in diff.header:
            if header.startswith("index ") and diff.target:
                index_lines[diff.target].append(header.split()[1])

    hunk_headers = [line for line in lines if line.startswith("@@")]
    return {
        "file": path.name,
        "bytes": len(raw),
        "lines": len(lines),
        "patch_eol": "CRLF" if patch_eol == "\r\n" else "LF",
        "non_ascii_bytes": sum(1 for byte in raw if byte > 127),
        "sections": len(diffs),
        "hunks": sum(len(diff.hunks) for diff in diffs),
        "hunk_header_forms": len({
            re.sub(r"\d+", "N", h.split("@@")[1])
            for h in hunk_headers if "@@" in h[2:]
        }),
        "new_files": [d.target for d in diffs if d.is_new],
        "deleted_files": [d.target for d in diffs if d.is_deleted],
        "binary_sections": [d.target for d in diffs if d.binary],
        "sections_without_hunks": [d.target for d in diffs if not d.hunks],
        "no_newline_markers": sum(1 for line in lines if line.startswith("\\")),
        "nested_paths": sorted({d.target for d in diffs if d.target and "/" in d.target}),
        "targets": [d.target for d in diffs if d.target],
        "index_lines": dict(index_lines),
    }


def discover(patch_dir: Path, patterns: list[str]) -> list[Path]:
    found: set[Path] = set()
    for pattern in patterns:
        found.update(p for p in patch_dir.glob(pattern) if p.is_file())
    return sorted(found, key=lambda p: p.name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch-dir", default=str(ROOT), help="directory with patch files")
    parser.add_argument("--patches", action="append", default=None,
                        help="glob(s), repeatable (default: *.patch *.diff)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    patches = discover(Path(args.patch_dir), args.patches or ["*.patch", "*.diff"])
    if not patches:
        print("no patch files found", file=sys.stderr)
        return 2

    reports = [inspect(path) for path in patches]
    owners: dict[str, set[str]] = defaultdict(set)
    transitions: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for report in reports:
        for target in report["targets"]:
            owners[target].add(report["file"])
        for target, blobs in report["index_lines"].items():
            transitions[target][report["file"]] = blobs

    shared = {target: sorted(files) for target, files in owners.items() if len(files) > 1}
    multi_version = {
        target: by_patch for target, by_patch in transitions.items() if len(by_patch) > 1
    }
    summary = {
        "patches": len(reports),
        "sections": sum(r["sections"] for r in reports),
        "hunks": sum(r["hunks"] for r in reports),
        "unique_targets": len(owners),
        "targets_in_multiple_patches": shared,
        "index_transitions_by_file": multi_version,
    }

    if args.json:
        print(json.dumps({"reports": reports, "summary": summary}, indent=2))
        return 0

    for report in reports:
        print(f"=== {report['file']} ===")
        print(f"  {report['bytes']} bytes, {report['lines']} lines, "
              f"{report['patch_eol']}, {report['non_ascii_bytes']} non-ASCII bytes")
        print(f"  sections: {report['sections']}, hunks: {report['hunks']}, "
              f"hunk header forms: {report['hunk_header_forms']}")
        print(f"  new: {len(report['new_files'])}, deleted: {len(report['deleted_files'])}, "
              f"binary: {len(report['binary_sections'])}, "
              f"without hunks: {len(report['sections_without_hunks'])}, "
              f"no-newline markers: {report['no_newline_markers']}")
        if report["nested_paths"]:
            print(f"  nested paths: {', '.join(report['nested_paths'])}")
    print("=== overall ===")
    print(f"  patches: {summary['patches']}, sections: {summary['sections']}, "
          f"hunks: {summary['hunks']}, unique targets: {summary['unique_targets']}")
    print(f"  targets in multiple patches: {len(shared)}")
    print(f"  files with different index blobs per patch: {len(multi_version)}")
    for target, by_patch in list(multi_version.items())[:5]:
        print(f"    {target}: " + ", ".join(
            f"{name[:8]}={','.join(blobs)}" for name, blobs in by_patch.items()
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
