import glob
import json
import os
import subprocess
import sys
import unittest

from tests.helpers import ROOT, SCRIPTS

sys.path.insert(0, SCRIPTS)
import arch_contract  # noqa: E402

SCRIPT = os.path.join(SCRIPTS, "arch_contract.py")


def rules(cjs: str) -> dict:
    return {r["name"]: r for r in arch_contract.config_json(cjs)["forbidden"]}


def run(args: list, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, SCRIPT] + args, input=stdin, capture_output=True, text=True, timeout=30)


class TemplatesTest(unittest.TestCase):
    def test_every_arch_has_template(self) -> None:
        names = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(arch_contract.TEMPLATES, "*.json"))}
        self.assertEqual(names, set(arch_contract.ARCHS) | {"base", "react-evolution.medium"})

    def test_rules_valid_and_bound_to_root(self) -> None:
        seen = set()
        for path in sorted(glob.glob(os.path.join(arch_contract.TEMPLATES, "*.json"))):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for rule in data["forbidden"]:
                where = "%s %s" % (os.path.basename(path), rule["name"])
                self.assertNotIn(rule["name"], seen, where)
                seen.add(rule["name"])
                self.assertIn(rule["severity"], ("error", "warn"), where)
                self.assertTrue(rule.get("comment"), where)
                self.assertNotIn("__ROOT__", json.dumps(rule).replace("__ROOT__/", ""), where)


class RenderTest(unittest.TestCase):
    def test_src_root(self) -> None:
        text = arch_contract.render_depcruise("react-fsd")
        self.assertTrue(text.startswith("// "))
        self.assertIn("module.exports = ", text)
        self.assertNotIn("__ROOT__", text)
        found = rules(text)
        self.assertEqual(found["fsd-layers-shared"]["from"]["path"], "^src/shared/")
        self.assertIn("no-circular", found)
        self.assertNotIn("tsConfig", arch_contract.config_json(text)["options"])

    def test_tsconfig(self) -> None:
        text = arch_contract.render_depcruise("react-fsd", tsconfig="tsconfig.app.json")
        self.assertEqual(arch_contract.config_json(text)["options"]["tsConfig"], {"fileName": "tsconfig.app.json"})

    def test_dot_root_drops_prefix(self) -> None:
        for root in (".", "", "./"):
            found = rules(arch_contract.render_depcruise("react-feature", root=root))
            self.assertEqual(found["feature-no-app"]["from"]["path"], "^features/", root)

    def test_root_with_regex_chars(self) -> None:
        found = rules(arch_contract.render_depcruise("react-feature", root="my.app/src/"))
        self.assertEqual(found["feature-no-app"]["from"]["path"], "^my\\.app/src/features/")

    def test_variant(self) -> None:
        self.assertNotIn("ed-cross-feature", rules(arch_contract.render_depcruise("react-evolution")))
        self.assertIn("ed-cross-feature", rules(arch_contract.render_depcruise("react-evolution", variant="medium")))

    def test_unknown(self) -> None:
        with self.assertRaises(FileNotFoundError):
            arch_contract.render_depcruise("react-mvc")
        with self.assertRaises(FileNotFoundError):
            arch_contract.render_depcruise("react-fsd", variant="medium")


class CountTest(unittest.TestCase):
    def test_count(self) -> None:
        self.assertEqual(arch_contract.count_violations(""), 0)
        self.assertEqual(arch_contract.count_violations("  \n"), 0)
        self.assertEqual(arch_contract.count_violations("[]"), 0)
        self.assertEqual(arch_contract.count_violations('[{"from": "a"}, {"from": "b"}]'), 2)
        with self.assertRaises(ValueError):
            arch_contract.count_violations("{}")

    def test_steiger_debt(self) -> None:
        text = json.dumps([
            {"ruleName": "fsd/no-segmentless-slices", "severity": "error"},
            {"ruleName": "fsd/no-segmentless-slices", "severity": "error"},
            {"ruleName": "fsd/forbidden-imports", "severity": "error"},
            {"ruleName": "fsd/insignificant-slice", "severity": "warn"},
        ])
        self.assertEqual(arch_contract.steiger_debt(text), ["fsd/forbidden-imports", "fsd/no-segmentless-slices"])
        self.assertEqual(arch_contract.steiger_debt(""), [])


class LintScriptTest(unittest.TestCase):
    def test_scripts(self) -> None:
        self.assertEqual(arch_contract.lint_script("react-fsd"), "depcruise src --ignore-known && steiger src")
        self.assertEqual(arch_contract.lint_script("nest-standard", root="."), "depcruise . --ignore-known")
        self.assertEqual(arch_contract.lint_script("react-evolution", root="src/", evo=True),
                         "depcruise src --ignore-known && edlint lint")


class CliTest(unittest.TestCase):
    def test_depcruise(self) -> None:
        proc = run(["depcruise", "--arch", "nest-standard", "--root", "src", "--tsconfig", "tsconfig.json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("nest-foreign-internals", rules(proc.stdout))

    def test_count_and_debt(self) -> None:
        self.assertEqual(run(["count"], "[{}, {}, {}]").stdout.strip(), "3")
        self.assertEqual(run(["steiger-debt"], '[{"ruleName": "fsd/x", "severity": "error"}]').stdout.strip(), "fsd/x")

    def test_lint_script(self) -> None:
        self.assertEqual(run(["lint-script", "--arch", "react-fsd"]).stdout.strip(),
                         "depcruise src --ignore-known && steiger src")

    def test_errors_exit_2(self) -> None:
        proc = run(["depcruise", "--arch", "react-mvc"])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("react-mvc", proc.stderr)
        self.assertEqual(run(["count"], "{}").returncode, 2)


class ParserTest(unittest.TestCase):
    def package(self, folder: str, version: str = None) -> str:
        if version:
            os.makedirs(os.path.join(folder, "node_modules", "typescript"))
            with open(os.path.join(folder, "node_modules", "typescript", "package.json"), "w") as f:
                json.dump({"name": "typescript", "version": version}, f)
        return folder

    def test_swc_for_typescript_7(self) -> None:
        import tempfile
        for version, expected in (("7.0.2", "swc"), ("8.1.0", "swc"), ("5.9.3", None), (None, None)):
            with tempfile.TemporaryDirectory() as folder:
                self.assertEqual(arch_contract.parser_for(self.package(folder, version)), expected, version)

    def test_typescript_found_up_the_tree(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            self.package(folder, "7.0.0")
            nested = os.path.join(folder, "apps", "web")
            os.makedirs(nested)
            self.assertEqual(arch_contract.parser_for(nested), "swc")

    def test_render_parser(self) -> None:
        options = arch_contract.config_json(arch_contract.render_depcruise("react-fsd", parser="swc"))["options"]
        self.assertEqual(options["parser"], "swc")
        self.assertNotIn("parser", arch_contract.config_json(arch_contract.render_depcruise("react-fsd"))["options"])

    def test_count_modules(self) -> None:
        self.assertEqual(arch_contract.count_modules('{"modules": [{"source": "a"}, {"source": "b"}]}'), 2)
        self.assertEqual(arch_contract.count_modules('{"modules": []}'), 0)
        with self.assertRaises(ValueError):
            arch_contract.count_modules("[]")

    def test_cli(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            self.package(folder, "7.0.2")
            self.assertEqual(run(["parser", folder]).stdout.strip(), "swc")
        proc = run(["depcruise", "--arch", "react-fsd", "--parser", "swc"])
        self.assertEqual(arch_contract.config_json(proc.stdout)["options"]["parser"], "swc")
        self.assertEqual(run(["modules"], '{"modules": [{}]}').stdout.strip(), "1")


class TsconfigTest(unittest.TestCase):
    def write(self, folder: str, name: str, data: str) -> None:
        with open(os.path.join(folder, name), "w") as f:
            f.write(data)

    def test_vite_references(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "tsconfig.json", '{"files": [], "references": [{"path": "./tsconfig.node.json"}, {"path": "./tsconfig.app.json"}]}')
            self.write(folder, "tsconfig.node.json", '{"compilerOptions": {}}')
            self.write(folder, "tsconfig.app.json", '{\n  // vite\n  "compilerOptions": {"paths": {"@/*": ["./src/*"]},},\n}')
            self.assertEqual(arch_contract.tsconfig_for(folder), "tsconfig.app.json")
            self.assertEqual(run(["tsconfig", folder]).stdout.strip(), "tsconfig.app.json")

    def test_plain_and_missing(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(arch_contract.tsconfig_for(folder))
            self.write(folder, "tsconfig.json", '{"compilerOptions": {"strict": true}}')
            self.assertEqual(arch_contract.tsconfig_for(folder), "tsconfig.json")
            self.write(folder, "tsconfig.json", '{"compilerOptions": {"paths": {"~/*": ["src/*"]}}}')
            self.assertEqual(arch_contract.tsconfig_for(folder), "tsconfig.json")


class UnresolvedTest(unittest.TestCase):
    def test_only_local_specifiers(self) -> None:
        dep = lambda module, bad: {"module": module, "resolved": module, "couldNotResolve": bad}
        text = json.dumps({"modules": [{"source": "src/a.ts", "dependencies": [
            dep("@/features/b", True), dep("./nope", True), dep("~/x", True), dep("#lib", True),
            dep("@prisma/client", True), dep("react", True), dep("./ok", False)]}]})
        self.assertEqual(arch_contract.unresolved_local(text),
                         ["src/a.ts -> @/features/b", "src/a.ts -> ./nope", "src/a.ts -> ~/x", "src/a.ts -> #lib"])
        proc = run(["unresolved"], text)
        self.assertEqual(proc.stdout.splitlines()[0], "4")


class IgnoreTest(unittest.TestCase):
    def test_glob_to_regex(self) -> None:
        import re
        cases = {"src/legacy/**": ("src/legacy/a/b.ts", "src/legacy2/a.ts"),
                 "src/**/*.stories.tsx": ("src/ui/button/x.stories.tsx", "src/ui/x.tsx"),
                 "src/old.ts": ("src/old.ts", "src/old.tsx")}
        for pattern, (hit, miss) in cases.items():
            regex = arch_contract.glob_regex(pattern)
            self.assertTrue(re.search(regex, hit), (pattern, regex, hit))
            self.assertFalse(re.search(regex, miss), (pattern, regex, miss))

    def test_render_and_cli(self) -> None:
        exclude = arch_contract.config_json(arch_contract.render_depcruise("react-fsd", ignore=["src/legacy/**"]))["options"]["exclude"]["path"]
        self.assertIsInstance(exclude, list)
        self.assertEqual(len(exclude), 2)
        self.assertIn(arch_contract.glob_regex("src/legacy/**"), exclude)
        proc = run(["depcruise", "--arch", "react-fsd", "--ignore", "src/legacy/**", "--ignore", "src/old.ts"])
        self.assertEqual(len(arch_contract.config_json(proc.stdout)["options"]["exclude"]["path"]), 3)
        plain = arch_contract.config_json(arch_contract.render_depcruise("react-fsd"))["options"]["exclude"]["path"]
        self.assertIsInstance(plain, str)


if __name__ == "__main__":
    unittest.main()
