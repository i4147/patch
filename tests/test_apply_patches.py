"""Tests for apply_patches.py.

Run from the repository root with::

    python -m unittest discover -s tests -v

The last test compares this implementation against ``git apply`` on the real
example patches in the repository (pre-images are reconstructed from the hunk
context/deletion lines, since the original .py sources are not checked in).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import apply_patches as ap  # noqa: E402

SCRIPT = ROOT / "apply_patches.py"


class PatchCase(unittest.TestCase):
    """A temp cwd holding patch files and source files, plus a runner."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def put(self, name: str, content: str, *, crlf: bool = False) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode("utf-8")
        if crlf:
            data = data.replace(b"\n", b"\r\n")
        path.write_bytes(data)
        return path

    def patch(self, name: str, content: str) -> Path:
        return self.put(name, content)

    def run_script(self, *args: str, cwd: Path | None = None):
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=cwd or self.root, capture_output=True, text=True)

    def output(self, name: str = "output") -> Path:
        return self.root / name


BASIC_PATCH = """\
diff --git a/a.py b/a.py
index 1111111..2222222 100644
--- a/a.py
+++ b/a.py
@@ -1,3 +1,4 @@
 line one
-line two
+line TWO
+extra
 line three
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1,2 +1,2 @@
 hello
-world
+there
diff --git a/missing.py b/missing.py
--- a/missing.py
+++ b/missing.py
@@ -1 +1 @@
-old
+new
"""


class TestGitStylePatches(PatchCase):
    def test_applies_to_existing_files_and_skips_missing(self):
        self.put("a.py", "line one\nline two\nline three\n")
        self.put("b.py", "hello\nworld\n")
        self.patch("change.patch", BASIC_PATCH)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(),
                         "line one\nline TWO\nextra\nline three\n")
        self.assertEqual(self.output("output/b.py").read_text(), "hello\nthere\n")
        self.assertFalse(self.output("output/missing.py").exists())
        self.assertIn("skipped missing: 1", result.stdout)
        # patch files are also accepted with a .diff extension
        self.patch("change2.diff", BASIC_PATCH)
        self.assertEqual(self.run_script("--patches", "*.diff", "--output-dir", "out2").returncode, 0)
        self.assertTrue(self.output("out2/a.py").exists())

    def test_defaults_use_current_working_directory(self):
        """No flags at all: patches and .py files in cwd, results in ./output."""
        self.put("a.py", "line one\nline two\nline three\n")
        self.patch("change.patch", BASIC_PATCH)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(),
                         "line one\nline TWO\nextra\nline three\n")

    def test_all_sources_missing_is_not_an_error(self):
        self.patch("change.patch", BASIC_PATCH)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output("output/a.py").exists())
        self.assertIn("applied: 0", result.stdout)

    def test_multiple_hunks_and_line_offsets(self):
        patch = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
 alpha
-beta
+BETA
@@ -4,2 +4,2 @@
 delta
-epsilon
+EPSILON
"""
        self.put("a.py", "X\nX\nX\nalpha\nbeta\ngamma\ndelta\nepsilon\nzeta\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(),
                         "X\nX\nX\nalpha\nBETA\ngamma\ndelta\nEPSILON\nzeta\n")

    def test_pure_insertion_hunk(self):
        patch = """\
--- a/a.py
+++ b/a.py
@@ -1,0 +2,2 @@
+inserted one
+inserted two
"""
        self.put("a.py", "first\nlast\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(),
                         "first\ninserted one\ninserted two\nlast\n")

    def test_plain_unified_diff_with_timestamps(self):
        patch = """\
--- a.py\t2024-01-01 10:00:00.000000000 +0000
+++ a.py\t2024-01-02 10:00:00.000000000 +0000
@@ -1,2 +1,2 @@
 keep
-old
+new
--- b.py\t2024-01-01 10:00:00.000000000 +0000
+++ b.py\t2024-01-02 10:00:00.000000000 +0000
@@ -1 +1 @@
-one
+two
"""
        self.put("a.py", "keep\nold\n")
        self.put("b.py", "one\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(), "keep\nnew\n")
        self.assertEqual(self.output("output/b.py").read_text(), "two\n")

    def test_mail_headers_and_signature_are_ignored(self):
        patch = """\
From abcdef Mon Sep 17 00:00:00 2001
Subject: [PATCH] tweak
---
 a.py | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+new
-- 
2.39.5
"""
        self.put("a.py", "old\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(), "new\n")


class TestSpecialSections(PatchCase):
    NEW_FILE_PATCH = """\
diff --git a/brand_new.py b/brand_new.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/brand_new.py
@@ -0,0 +1,3 @@
+#!/usr/bin/env python3
+print("created")
+
"""

    def test_new_file_skipped_by_default(self):
        self.patch("p.patch", self.NEW_FILE_PATCH)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output("output/brand_new.py").exists())
        self.assertIn("skipped missing: 1", result.stdout)

    def test_new_file_created_on_request(self):
        self.patch("p.patch", self.NEW_FILE_PATCH)
        result = self.run_script("--new-files", "create")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/brand_new.py").read_text(),
                         '#!/usr/bin/env python3\nprint("created")\n\n')

    def test_deletion_removes_output(self):
        patch = """\
diff --git a/gone.py b/gone.py
deleted file mode 100644
index 1111111..0000000
--- a/gone.py
+++ /dev/null
@@ -1 +0,0 @@
-bye
"""
        self.put("gone.py", "bye\n")
        self.put("output/gone.py", "stale\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output("output/gone.py").exists())

    def test_binary_section_is_skipped(self):
        patch = """\
diff --git a/image.bin b/image.bin
index 1111111..2222222 100644
Binary files a/image.bin and b/image.bin differ
"""
        self.put("image.bin", "binary")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output("output/image.bin").exists())

    def test_mode_only_section_copies_file(self):
        patch = """\
diff --git a/a.py b/a.py
old mode 100644
new mode 100755
"""
        self.put("a.py", "unchanged\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(), "unchanged\n")

    def test_unsafe_paths_are_rejected(self):
        patch = """\
diff --git a/../../evil.py b/../../evil.py
--- a/../../evil.py
+++ b/../../evil.py
@@ -1 +1 @@
-old
+new
"""
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root.parent / "evil.py").exists())

    def test_quoted_path_with_space(self):
        patch = '''\
diff --git "a/my file.py" "b/my file.py"
--- "a/my file.py"
+++ "b/my file.py"
@@ -1 +1 @@
-old
+new
'''
        self.put("my file.py", "old\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/my file.py").read_text(), "new\n")

    def test_subdirectory_paths(self):
        patch = """\
diff --git a/tools/helper.py b/tools/helper.py
--- a/tools/helper.py
+++ b/tools/helper.py
@@ -1 +1 @@
-old
+new
"""
        self.put("tools/helper.py", "old\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/tools/helper.py").read_text(), "new\n")


class TestTextDetails(PatchCase):
    def test_no_newline_at_end_of_file(self):
        patch = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
 a
-b
+B
\\ No newline at end of file
"""
        self.put("a.py", "a\nb\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_bytes(), b"a\nB")

    def test_no_newline_marker_on_removed_line(self):
        patch = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,3 @@
 a
-b
\\ No newline at end of file
+b
+c
"""
        self.put("a.py", "a\nb")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_bytes(), b"a\nb\nc\n")

    def test_crlf_line_endings_are_preserved(self):
        patch = "\n".join([
            "diff --git a/a.py b/a.py",
            "--- a/a.py",
            "+++ b/a.py",
            "@@ -1,2 +1,2 @@",
            " a\r",
            "-b\r",
            "+B\r",
            "",
        ])
        (self.root / "a.py").write_bytes(b"a\r\nb\r\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_bytes(), b"a\r\nB\r\n")

    def test_unicode_content(self):
        patch = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
 café
-mañana
+mañana ☕
"""
        self.put("a.py", "café\nmañana\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(), "café\nmañana ☕\n")

    def test_blank_context_lines(self):
        patch = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,3 +1,3 @@
 
-old
+new
 
"""
        self.put("a.py", "\nold\n\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(), "\nnew\n\n")

    def test_deletion_lines_that_look_like_headers(self):
        # "--- a/foo" is a removal of the text "-- a/foo", not a new header.
        patch = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
 keep
--- a/foo
+replacement
"""
        self.put("a.py", "keep\n-- a/foo\n")
        self.patch("p.patch", patch)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(), "keep\nreplacement\n")


class TestCliBehaviour(PatchCase):
    def test_dry_run_writes_nothing(self):
        self.put("a.py", "line one\nline two\nline three\n")
        self.patch("p.patch", BASIC_PATCH)
        result = self.run_script("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output("output/a.py").exists())

    def test_clean_removes_stale_output(self):
        self.put("a.py", "line one\nline two\nline three\n")
        self.put("output/stale.py", "old\n")
        self.patch("p.patch", BASIC_PATCH)
        result = self.run_script("--clean")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output("output/stale.py").exists())
        self.assertTrue(self.output("output/a.py").exists())

    def test_layout_by_patch_keeps_every_result(self):
        self.put("a.py", "old\n")
        self.patch("one.patch", """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+ONE
""")
        self.patch("two.patch", """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+TWO
""")
        result = self.run_script("--layout", "by-patch")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/one/a.py").read_text(), "ONE\n")
        self.assertEqual(self.output("output/two/a.py").read_text(), "TWO\n")
        self.assertFalse(self.output("output/a.py").exists())

    def test_auto_layout_keeps_both_on_collision(self):
        self.put("a.py", "old\n")
        self.patch("one.patch", """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+ONE
""")
        self.patch("two.patch", """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+TWO
""")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(), "TWO\n")
        self.assertEqual(self.output("output/one/a.py").read_text(), "ONE\n")
        self.assertEqual(self.output("output/two/a.py").read_text(), "TWO\n")
        self.assertIn("also saved per patch", result.stdout)

    def test_mismatched_source_is_reported_and_strict_exits_1(self):
        self.put("a.py", "totally different\n")
        self.patch("p.patch", BASIC_PATCH)
        result = self.run_script()
        self.assertEqual(result.returncode, 0)  # non-fatal by default
        self.assertIn("failed: 1", result.stdout)
        self.assertIn("FAIL", result.stderr)
        self.assertFalse(self.output("output/a.py").exists())
        strict = self.run_script("--strict")
        self.assertEqual(strict.returncode, 1)

    def test_ignore_whitespace_allows_indentation_drift(self):
        patch = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
 def f():
-    return 1
+    return 2
"""
        self.put("a.py", "def f():\n        return 1\n")
        self.patch("p.patch", patch)
        strict_default = self.run_script()
        self.assertEqual(strict_default.returncode, 0)
        self.assertIn("failed: 1", strict_default.stdout)
        self.assertFalse(self.output("output/a.py").exists())
        result = self.run_script("--ignore-whitespace", "--clean")
        self.assertEqual(result.returncode, 0, result.stderr)
        # matching ignores indentation, added lines keep the patch's own text
        self.assertEqual(self.output("output/a.py").read_text(), "def f():\n    return 2\n")

    def test_positional_patch_files_and_ignored_py_names(self):
        self.put("a.py", "line one\nline two\nline three\n")
        self.patch("p.patch", BASIC_PATCH)
        result = self.run_script("p.patch", "a.py")  # shell-glob style invocation
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("output/a.py").read_text(),
                         "line one\nline TWO\nextra\nline three\n")

    def test_no_patch_files_returns_2(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIn("no patch files", result.stderr)

    def test_explicit_directories(self):
        self.put("src/a.py", "line one\nline two\nline three\n")
        self.put("patches/p.patch", BASIC_PATCH)
        result = self.run_script("--patch-dir", "patches", "--source-dir", "src",
                                 "--output-dir", "results")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output("results/a.py").read_text(),
                         "line one\nline TWO\nextra\nline three\n")


class TestAgainstGitApply(PatchCase):
    """Byte-for-byte comparison with git apply on the repository's examples."""

    @staticmethod
    def reconstruct(diffs):
        files = {}
        for diff in diffs:
            if diff.old_path is None or not diff.hunks:
                continue
            placed = {}
            for hunk in diff.hunks:
                for i, line in enumerate(hunk.old_lines):
                    index = hunk.anchor + i
                    text = line.text + "\n"
                    if index in placed and placed[index] != text:
                        raise AssertionError(f"conflicting pre-image {diff.old_path}:{index}")
                    placed[index] = text
            if placed:
                size = max(placed) + 1
                files[diff.old_path] = "".join(
                    placed.get(i, f"FILLER_{i}\n") for i in range(size)
                )
            else:
                files[diff.old_path] = ""
        return files

    @unittest.skipUnless(shutil.which("git"), "git is not installed")
    def test_real_patches_match_git_apply(self):
        patches = sorted(ROOT.glob("*.patch"))
        if not patches:
            self.skipTest("example patches are not available")
        for patch in patches:
            with self.subTest(patch=patch.name):
                diffs, _ = ap.parse_patch(ap.read_text(patch))
                pre = self.reconstruct(diffs)
                reference = self.root / "reference"
                mine = self.root / "mine"
                reference.mkdir(exist_ok=True)
                mine.mkdir(exist_ok=True)
                for base in (reference, mine):
                    for rel, content in pre.items():
                        target = base / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(content.encode("utf-8"))
                git = subprocess.run(["git", "apply", "-p1", str(patch)],
                                     cwd=reference, capture_output=True, text=True)
                self.assertEqual(git.returncode, 0, git.stderr)
                run = self.run_script("--patch-dir", str(patch.parent),
                                      "--patches", patch.name,
                                      "--source-dir", str(mine),
                                      "--output-dir", str(mine / "output"),
                                      "--new-files", "create", "--layout", "flat",
                                      "--clean")
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertIn("failed: 0", run.stdout)
                expected = {d.target for d in diffs if d.target and not d.is_deleted}
                got = {str(p.relative_to(mine / "output"))
                       for p in (mine / "output").rglob("*") if p.is_file()}
                self.assertEqual(got, expected)
                for rel in expected:
                    self.assertEqual((mine / "output" / rel).read_bytes(),
                                     (reference / rel).read_bytes(), rel)
                shutil.rmtree(reference)
                shutil.rmtree(mine)


class TestParserUnits(unittest.TestCase):
    def test_hunk_counts_and_paths(self):
        diffs, eol = ap.parse_patch(BASIC_PATCH)
        self.assertEqual(eol, "\n")
        self.assertEqual([d.target for d in diffs], ["a.py", "b.py", "missing.py"])
        self.assertEqual(diffs[0].hunks[0].old_count, 3)
        self.assertEqual(diffs[0].hunks[0].new_count, 4)
        self.assertEqual(len(diffs[0].hunks[0].lines), 5)

    def test_split_lines_round_trip(self):
        for text in ("", "a", "a\n", "a\nb\n", "a\r\nb\r\n", "a\n\n"):
            self.assertEqual(ap.render(ap.split_lines(text)), text)

    def test_unquote_path(self):
        self.assertEqual(ap.unquote_path('"a/my\\040file.py"'), "a/my file.py")
        self.assertEqual(ap.clean_path("/dev/null"), None)
        self.assertEqual(ap.safe_relative("../../x.py"), None)
        self.assertEqual(ap.safe_relative("tools/x.py"), "tools/x.py")


if __name__ == "__main__":
    unittest.main()
