import glob
import os
import re
import unittest

from tests.helpers import ROOT

REF_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+\.(?:md|py))")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
STACK_SKILLS = {"typescript", "node", "python", "docker", "nginx"}
ADAPTED = {
    "refs/codebase-design.md": "skills/engineering/codebase-design/SKILL.md",
    "skills/codebase-design/DEEPENING.md": "skills/engineering/codebase-design/DEEPENING.md",
    "skills/codebase-design/DESIGN-IT-TWICE.md": "skills/engineering/codebase-design/DESIGN-IT-TWICE.md",
    "skills/writing-for-agents/SKILL.md": "skills/productivity/writing-for-agents/SKILL.md",
    "skills/writing-for-agents/SKILL-MECHANICS.md": "skills/productivity/writing-for-agents/SKILL-MECHANICS.md",
    "refs/grilling.md": "skills/productivity/grilling/SKILL.md",
    "commands/handoff.md": "skills/productivity/handoff/SKILL.md",
    "commands/architecture.md": "skills/engineering/improve-codebase-architecture/SKILL.md",
    "refs/architecture-report.md": "skills/engineering/improve-codebase-architecture/HTML-REPORT.md",
}


def texts() -> list:
    found = glob.glob(os.path.join(ROOT, "refs", "**", "*.md"), recursive=True)
    found += glob.glob(os.path.join(ROOT, "commands", "*.md"))
    return sorted(found + glob.glob(os.path.join(ROOT, "skills", "**", "*.md"), recursive=True))


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
                 "pr-structure.md", "stack-typescript.md", "stack-node.md", "stack-python.md", "stack-docker.md",
                 "stack-nginx.md"}
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

    def test_skill_frontmatter(self) -> None:
        skills = glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md"))
        self.assertTrue(STACK_SKILLS <= {os.path.basename(os.path.dirname(p)) for p in skills})
        for path in skills:
            with open(path, encoding="utf-8") as f:
                match = FRONTMATTER_RE.match(f.read())
            self.assertIsNotNone(match, path)
            fields = dict(line.split(": ", 1) for line in match.group(1).splitlines() if ": " in line)
            self.assertEqual(fields.get("name"), os.path.basename(os.path.dirname(path)), path)
            description = fields.get("description", "")
            self.assertTrue(0 < len(description) <= 120, path)
            self.assertNotIn(":", description, path)

    def test_adapted_files_credit_source(self) -> None:
        for rel, source in ADAPTED.items():
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                self.assertIn("Адаптировано из mattpocock/skills (MIT), `%s`." % source, f.read(), rel)

    def test_new_commands_are_manual_only(self) -> None:
        for name in ("grill.md", "handoff.md", "architecture.md", "arch.md", "note.md"):
            path = os.path.join(ROOT, "commands", name)
            if not os.path.exists(path):
                self.fail("нет %s" % name)
            with open(path, encoding="utf-8") as f:
                self.assertIn("disable-model-invocation: true", f.read(), name)

    def test_review_and_check_cover_stacks(self) -> None:
        with open(os.path.join(ROOT, "commands", "review.md"), encoding="utf-8") as f:
            review = f.read()
        for name in ("stack-typescript.md", "stack-node.md", "stack-python.md", "stack-docker.md", "stack-nginx.md",
                     "codebase-design.md"):
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/refs/" + name, review, name)
        with open(os.path.join(ROOT, "commands", "check.md"), encoding="utf-8") as f:
            check = f.read()
        for word in ("ruff check", "pytest", "hadolint", "docker compose", "nginx -t", "biome", "oxlint"):
            self.assertIn(word, check, word)


    def test_writing_for_agents_yields_to_writing_skills(self) -> None:
        with open(os.path.join(ROOT, "skills", "writing-for-agents", "SKILL.md"), encoding="utf-8") as f:
            self.assertIn("При расхождении прав `superpowers:writing-skills`", f.read())

    def test_arch_command(self) -> None:
        with open(os.path.join(ROOT, "commands", "arch.md"), encoding="utf-8") as f:
            text = f.read()
        for word in ("scripts/arch_detect.py", "scripts/arch_contract.py", "--output-type baseline",
                     "steiger-debt", "lint-script", "`[]`", "arch_contract.py parser", "--parser swc", "@swc/core",
                     "arch_contract.py modules", "arch_contract.py tsconfig", "arch_contract.py unresolved",
                     "--ignore", "cd <пакет>", "нет бинаря", "TS18003", "## init", "## detect", "## check", "ARCHITECTURE.md"):
            self.assertIn(word, text, word)
        with open(os.path.join(ROOT, "skills", "arch-rules", "SKILL.md"), encoding="utf-8") as f:
            skill = f.read()
        self.assertIn("ARCHITECTURE.md", skill)
        self.assertIn("lint:arch", skill)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "refs", "arch", "steiger.config.ts")))

    def test_note_command(self) -> None:
        with open(os.path.join(ROOT, "commands", "note.md"), encoding="utf-8") as f:
            text = f.read()
        for word in ("DEVKIT_NOTES", "Как писать конспекты.md", "Шаблоны/Конспект.md", "черновик", "#проверить"):
            self.assertIn(word, text, word)
        with open(os.path.join(ROOT, "commands", "commands.md"), encoding="utf-8") as f:
            self.assertIn("/note <тема>", f.read())
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            self.assertIn("DEVKIT_NOTES", f.read())

    def test_review_and_check_read_arch_contract(self) -> None:
        with open(os.path.join(ROOT, "commands", "review.md"), encoding="utf-8") as f:
            review = f.read()
        self.assertIn("ARCHITECTURE.md", review)
        self.assertIn(".dependency-cruiser-known-violations.json", review)
        with open(os.path.join(ROOT, "commands", "check.md"), encoding="utf-8") as f:
            check = f.read()
        for word in ("lint:arch", "arch_contract.py modules", "arch_contract.py unresolved", "depcruise"):
            self.assertIn(word, check, word)
        for name in ("review-react.md", "review-nest.md"):
            with open(os.path.join(ROOT, "refs", name), encoding="utf-8") as f:
                self.assertIn("ARCHITECTURE.md", f.read(), name)
        with open(os.path.join(ROOT, "commands", "commands.md"), encoding="utf-8") as f:
            self.assertIn("/arch init|detect|check", f.read())
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            self.assertIn("/arch", f.read())


if __name__ == "__main__":
    unittest.main()
