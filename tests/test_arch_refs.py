import json
import os
import re
import unittest

from tests.helpers import ROOT

ARCH = os.path.join(ROOT, "refs", "arch")
TEMPLATES = os.path.join(ARCH, "depcruise")
REACT = ["react-fsd", "react-feod", "react-evolution", "react-feature", "react-clean"]
NEST = ["nest-standard", "nest-modular-clean", "nest-ddd-cqrs"]
IDS = REACT + NEST
SECTIONS = ["Когда брать", "Дерево", "Импорты", "Public API", "Куда класть", "Антипаттерны", "Признаки", "Источники"]
SIGNATURE_KEYS = {"requires_dep", "dirs_all", "dirs_any", "dirs_none", "files_any", "bonus_files", "weight"}


def read(name: str) -> str:
    with open(os.path.join(ARCH, name), encoding="utf-8") as f:
        return f.read()


def section(text: str, name: str) -> str:
    match = re.search(r"^## %s\n(.*?)(?=^## |\Z)" % re.escape(name), text, re.S | re.M)
    return match.group(1) if match else ""


def signature(text: str) -> dict:
    match = re.search(r"```json\n(.*?)\n```", section(text, "Признаки"), re.S)
    return json.loads(match.group(1)) if match else {}


def rule_names(arch: str) -> list:
    names = []
    for suffix in ("", ".small", ".medium"):
        path = os.path.join(TEMPLATES, arch + suffix + ".json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                names += [r["name"] for r in json.load(f)["forbidden"]]
    return names


class ArchRefsTest(unittest.TestCase):
    def test_sections_in_order(self) -> None:
        for arch in IDS:
            headings = re.findall(r"^## (.+)$", read(arch + ".md"), re.M)
            self.assertEqual(headings, SECTIONS, arch)

    def test_signature(self) -> None:
        for arch in IDS:
            sig = signature(read(arch + ".md"))
            self.assertEqual(set(sig), SIGNATURE_KEYS, arch)
            self.assertTrue(sig["requires_dep"], arch)
            self.assertTrue(sig["dirs_all"] or sig["dirs_any"] or sig["files_any"], arch)

    def test_every_rule_explained(self) -> None:
        for arch in IDS:
            text = read(arch + ".md")
            for name in rule_names(arch):
                self.assertIn("`%s`" % name, text, "%s %s" % (arch, name))

    def test_sources_are_links(self) -> None:
        for arch in IDS + ["catalog"]:
            self.assertIn("https://", section(read(arch + ".md"), "Источники") if arch != "catalog"
                          else section(read("catalog.md"), "Кто так делает"), arch)

    def test_catalog(self) -> None:
        text = read("catalog.md")
        self.assertEqual(re.findall(r"^## (.+)$", text, re.M), ["Вопросы", "Рекомендации", "Кто так делает"])
        for arch in IDS:
            self.assertIn("`%s`" % arch, section(text, "Рекомендации"), arch)
        for name in ("Климов", "Primeagen"):
            self.assertNotIn(name, text)

    def test_refs_match_templates(self) -> None:
        templates = {name[:-5] for name in os.listdir(TEMPLATES)
                     if name.endswith(".json") and name != "base.json" and name.count(".") == 1}
        self.assertEqual(templates, set(IDS))
        refs = {name[:-3] for name in os.listdir(ARCH) if name.endswith(".md") and name != "catalog.md"}
        self.assertEqual(refs, set(IDS))


if __name__ == "__main__":
    unittest.main()
