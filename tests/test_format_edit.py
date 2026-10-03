import json
import os
import unittest

from tests.helpers import HookTestCase

FAKE_PRETTIER = "#!/bin/sh\necho prettier \"$@\" >> \"$(dirname \"$0\")/../../calls.log\"\n"
FAKE_ESLINT_FAIL = "#!/bin/sh\necho \"  3:1  error  'x' is not defined  no-undef\"\nexit 1\n"
FAKE_ESLINT_OK = "#!/bin/sh\nexit 0\n"
FAKE_ESLINT_CONFIG_ERROR = "#!/bin/sh\necho 'Oops config' >&2\nexit 2\n"

FAKE_LOGGER = "#!/bin/sh\necho \"$(basename \"$0\") $@\" >> \"%s/calls.log\"\nexit %d\n"

FAKE_PRETTIER_PWD = "#!/bin/sh\npwd > \"$(dirname \"$0\")/../../prettier_cwd.log\"\n"


class FormatEditTest(HookTestCase):
    def project(self, eslint: str) -> str:
        self.write("proj/eslint.config.mjs", "export default []\n")
        self.write("proj/node_modules/.bin/prettier", FAKE_PRETTIER, executable=True)
        self.write("proj/node_modules/.bin/eslint", eslint, executable=True)
        return self.write("proj/src/a.ts", "const a = 1\n")

    def payload(self, path: str) -> dict:
        return {"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "Edit",
                "tool_input": {"file_path": path}}

    def edited(self) -> list:
        with open(os.path.join(self.home, ".claude/devkit/state/s1.json")) as f:
            return json.load(f).get("edited", [])

    def test_runs_prettier_and_records_ts_file(self) -> None:
        path = self.project(FAKE_ESLINT_OK)
        code, out, err = self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual((code, out, err), (0, "", ""))
        with open(os.path.join(self.home, "proj/calls.log")) as f:
            self.assertIn("--write", f.read())
        self.assertEqual(self.edited(), [os.path.realpath(path)])

    def test_records_file_once(self) -> None:
        path = self.project(FAKE_ESLINT_OK)
        self.run_hook("format_edit.py", self.payload(path))
        self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual(len(self.edited()), 1)

    def test_eslint_errors_go_back_to_claude(self) -> None:
        path = self.project(FAKE_ESLINT_FAIL)
        code, _, err = self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual(code, 2)
        self.assertIn("no-undef", err)

    def test_eslint_config_error_does_not_block(self) -> None:
        path = self.project(FAKE_ESLINT_CONFIG_ERROR)
        code, _, _ = self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual(code, 0)

    def test_project_without_tools_is_silent(self) -> None:
        path = self.write("bare/src/a.ts", "x\n")
        code, out, err = self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual((code, out, err), (0, "", ""))

    def test_skips_node_modules_and_generated(self) -> None:
        self.project(FAKE_ESLINT_FAIL)
        for rel in ("proj/node_modules/x/a.ts", "proj/src/__generated__/g.ts", "proj/src/api.generated.ts"):
            path = self.write(rel, "x\n")
            code, _, _ = self.run_hook("format_edit.py", self.payload(path))
            self.assertEqual(code, 0, rel)

    def test_prettier_runs_from_prettierignore_dir(self) -> None:
        self.write("mono/.prettierignore", "apps/web/src/gen.ts\n")
        self.write("mono/node_modules/.bin/prettier", FAKE_PRETTIER_PWD, executable=True)
        path = self.write("mono/apps/web/src/gen.ts", "x\n")
        self.run_hook("format_edit.py", self.payload(path))
        with open(os.path.join(self.home, "mono/prettier_cwd.log")) as f:
            self.assertEqual(os.path.realpath(f.read().strip()), os.path.join(self.home, "mono"))

    def test_format_switch_off_still_records(self) -> None:
        path = self.project(FAKE_ESLINT_FAIL)
        code, _, _ = self.run_hook("format_edit.py", self.payload(path), env={"DEVKIT_FORMAT": "0"})
        self.assertEqual(code, 0)
        self.assertEqual(self.edited(), [os.path.realpath(path)])

    def logger(self, rel: str, code: int = 0, out: str = "") -> str:
        body = FAKE_LOGGER % (self.home, code)
        if out:
            body = body.replace("exit", "echo \"%s\"\nexit" % out)
        return self.write(rel, body, executable=True)

    def calls(self) -> str:
        path = os.path.join(self.home, "calls.log")
        return open(path).read() if os.path.exists(path) else ""

    def test_biome_replaces_prettier_and_eslint(self) -> None:
        self.write("b/biome.json", "{}")
        self.logger("b/node_modules/.bin/biome")
        self.logger("b/node_modules/.bin/prettier")
        self.logger("b/node_modules/.bin/eslint")
        self.write("b/eslint.config.mjs", "export default []\n")
        path = self.write("b/src/a.ts", "x\n")
        code, _, _ = self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual(code, 0)
        self.assertIn("biome check --write", self.calls())
        self.assertNotIn("prettier", self.calls())
        self.assertNotIn("eslint", self.calls())

    def test_biome_errors_block(self) -> None:
        self.write("b/biome.json", "{}")
        self.logger("b/node_modules/.bin/biome", code=1, out="lint/suspicious/noExplicitAny")
        path = self.write("b/src/a.ts", "x\n")
        code, _, err = self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual(code, 2)
        self.assertIn("noExplicitAny", err)

    def test_oxlint_runs_before_eslint_and_blocks(self) -> None:
        path = self.project(FAKE_ESLINT_OK)
        self.write("proj/.oxlintrc.json", "{}")
        self.logger("proj/node_modules/.bin/oxlint", code=1, out="eslint(no-unused-vars)")
        code, _, err = self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual(code, 2)
        self.assertIn("oxlint --fix", self.calls())
        self.assertIn("no-unused-vars", err)

    def test_js_recorded_only_with_tests_opt_in(self) -> None:
        path = self.write("bare/src/a.js", "x\n")
        self.run_hook("format_edit.py", self.payload(path))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude/devkit/state/s1.json")) and self.edited())
        self.run_hook("format_edit.py", self.payload(path), env={"DEVKIT_TESTS": "1"})
        self.assertEqual(self.edited(), [os.path.realpath(path)])

    def test_python_file_recorded(self) -> None:
        path = self.write("py/app/a.py", "x\n")
        self.run_hook("format_edit.py", self.payload(path), env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(self.edited(), [os.path.realpath(path)])

    def test_skips_venv_and_pycache(self) -> None:
        for rel in ("py/.venv/lib/x.py", "py/app/__pycache__/x.py"):
            path = self.write(rel, "x\n")
            code, out, err = self.run_hook("format_edit.py", self.payload(path))
            self.assertEqual((code, out, err), (0, "", ""), rel)


FAKE_GIXY_HIGH = """#!/bin/sh
echo '[{"plugin": "host_spoofing", "summary": "Host header forgery", "severity": "HIGH"}, {"plugin": "add_header_redefinition", "summary": "Nested add_header", "severity": "MEDIUM"}]'
exit 1
"""
FAKE_GIXY_LOW = """#!/bin/sh
echo '[{"plugin": "add_header_redefinition", "summary": "Nested add_header", "severity": "MEDIUM"}]'
exit 1
"""


class StackChecksTest(HookTestCase):
    def payload(self, path: str) -> dict:
        return {"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "Edit",
                "tool_input": {"file_path": path}}

    def fake(self, name: str, code: int = 0, out: str = "", err: str = "") -> None:
        body = "#!/bin/sh\necho \"%s $@\" >> \"%s/calls.log\"\n" % (name, self.home)
        if out:
            body += "echo '%s'\n" % out
        if err:
            body += "echo '%s' >&2\n" % err
        self.write("bin/" + name, body + "exit %d\n" % code, executable=True)

    def hook(self, path: str):
        env = {"PATH": "%s/bin:/usr/bin:/bin" % self.home}
        return self.run_hook("format_edit.py", self.payload(path), env=env)

    def calls(self) -> str:
        path = os.path.join(self.home, "calls.log")
        return open(path).read() if os.path.exists(path) else ""

    def test_ruff_without_config_does_nothing(self) -> None:
        self.fake("ruff", code=1, out="E501")
        path = self.write("py/app/a.py", "x\n")
        self.assertEqual(self.hook(path)[0], 0)
        self.assertEqual(self.calls(), "")

    def test_ruff_formats_and_blocks_on_remaining_errors(self) -> None:
        self.write("py/pyproject.toml", "[tool.ruff]\nline-length = 100\n")
        self.fake("ruff", code=1, out="app/a.py:1:1: F401 unused import")
        path = self.write("py/app/a.py", "x\n")
        code, _, err = self.hook(path)
        self.assertEqual(code, 2)
        self.assertIn("ruff format", self.calls())
        self.assertIn("ruff check --fix", self.calls())
        self.assertIn("F401", err)

    def test_ruff_from_venv_wins(self) -> None:
        self.write("py/ruff.toml", "")
        self.fake("ruff", code=1, out="GLOBAL")
        self.write("py/.venv/bin/ruff", "#!/bin/sh\nexit 0\n", executable=True)
        path = self.write("py/app/a.py", "x\n")
        self.assertEqual(self.hook(path)[0], 0)

    def test_hadolint_blocks_on_error(self) -> None:
        self.fake("hadolint", code=1, out="DL3006 error: Always tag the version of an image explicitly")
        path = self.write("d/Dockerfile", "FROM node\n")
        code, _, err = self.hook(path)
        self.assertEqual(code, 2)
        self.assertIn("--failure-threshold error", self.calls())
        self.assertIn("DL3006", err)

    def test_dockerfile_without_hadolint_is_silent(self) -> None:
        path = self.write("d/Dockerfile", "FROM node\n")
        self.assertEqual(self.hook(path), (0, "", ""))

    def test_compose_error_blocks(self) -> None:
        self.fake("docker", code=15, err="yaml: line 3: mapping values are not allowed in this context")
        path = self.write("c/compose.yaml", "services:\n  a: b: c\n")
        code, _, err = self.hook(path)
        self.assertEqual(code, 2)
        self.assertIn("mapping values", err)

    def test_compose_override_checked_with_base(self) -> None:
        self.fake("docker")
        base = self.write("c/docker-compose.yml", "services: {}\n")
        override = self.write("c/docker-compose.override.yml", "services: {}\n")
        self.assertEqual(self.hook(override)[0], 0)
        self.assertIn("compose -f %s -f %s config -q" % (base, override), self.calls())

    def test_compose_missing_env_does_not_block(self) -> None:
        for message in ("env file /x/.env not found: stat /x/.env: no such file or directory",
                        'required variable DB_PASSWORD is missing a value: set it'):
            self.fake("docker", code=1, err=message)
            path = self.write("c/compose.yaml", "services: {}\n")
            self.assertEqual(self.hook(path)[0], 0, message)

    def test_docker_without_compose_plugin_does_not_block(self) -> None:
        self.fake("docker", code=125, err="unknown shorthand flag: 'f' in -f")
        path = self.write("c/compose.yaml", "services: {}\n")
        self.assertEqual(self.hook(path)[0], 0)

    def test_lone_override_without_base_does_not_block(self) -> None:
        self.fake("docker", code=1, err='service "web" has neither an image nor a build context specified: invalid compose project')
        path = self.write("c/docker-compose.prod.yml", "services:\n  web:\n    ports: ['80:80']\n")
        self.assertEqual(self.hook(path)[0], 0)

    def test_gixy_blocks_only_on_high(self) -> None:
        self.write("bin/gixy", FAKE_GIXY_HIGH, executable=True)
        path = self.write("n/nginx.conf", "events {}\n")
        code, _, err = self.hook(path)
        self.assertEqual(code, 2)
        self.assertIn("host_spoofing", err)
        self.assertNotIn("add_header_redefinition", err)
        self.write("bin/gixy", FAKE_GIXY_LOW, executable=True)
        self.assertEqual(self.hook(path)[0], 0)


class TimeoutBudgetTest(unittest.TestCase):
    def test_js_tools_fit_hook_timeout(self) -> None:
        import sys
        from tests.helpers import HOOKS
        sys.path.insert(0, HOOKS)
        import format_edit
        with open(os.path.join(HOOKS, "hooks.json")) as f:
            post = json.load(f)["hooks"]["PostToolUse"][0]["hooks"][0]["timeout"]
        total = format_edit.PRETTIER_TIMEOUT + format_edit.OXLINT_TIMEOUT + format_edit.ESLINT_TIMEOUT
        self.assertLess(total, post)


if __name__ == "__main__":
    unittest.main()
