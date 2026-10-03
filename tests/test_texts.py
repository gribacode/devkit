import glob
import os
import re
import unittest

from tests.helpers import ROOT

REF_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+\.(?:md|py))")


def texts() -> list:
    return sorted(glob.glob(os.path.join(ROOT, "refs", "*.md")) + glob.glob(os.path.join(ROOT, "commands", "*.md")))


def prose_lines(path: str) -> list:
    lines, in_code = [], False
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            if line.lstrip().startswith(("```", "~~~")):
                in_code = not in_code
                continue
            if not in_code:
                lines.append((number, re.sub(r"`[^`]*`", "", line)))
    return lines


class TextsTest(unittest.TestCase):
    def test_refs_exist(self) -> None:
        names = {"style.md", "review-principles.md", "review-react.md", "review-nest.md", "review-shared.md",
                 "pr-structure.md"}
        self.assertTrue(names <= {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "refs", "*.md"))})

    def test_no_yo_and_no_dashes_in_prose(self) -> None:
        for path in texts():
            for number, line in prose_lines(path):
                where = "%s:%d" % (os.path.relpath(path, ROOT), number)
                self.assertNotIn("ё", line.lower(), where)
                self.assertNotIn("—", line, where)
                self.assertNotIn("–", line, where)
                self.assertIsNone(re.search(r"\s-\s", line), where)

    def test_plugin_root_links_resolve(self) -> None:
        for path in texts():
            with open(path, encoding="utf-8") as f:
                for rel in REF_RE.findall(f.read()):
                    self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)), "%s -> %s" % (path, rel))

    def test_review_and_pr_diff_against_remote_base(self) -> None:
        for name in ("review.md", "pr.md"):
            with open(os.path.join(ROOT, "commands", name), encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn("часть после `origin/`", text, name)
            self.assertIn("origin/<ветка>", text, name)

    def test_pr_create_command_does_not_wait_for_stdin(self) -> None:
        with open(os.path.join(ROOT, "commands", "pr.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("--body-file -", text)
        self.assertIn("без префикса `origin/`", text)


if __name__ == "__main__":
    unittest.main()
