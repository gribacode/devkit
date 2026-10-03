import json
import os
import unittest

from tests.helpers import HookTestCase

FAKE_PRETTIER = "#!/bin/sh\necho prettier \"$@\" >> \"$(dirname \"$0\")/../../calls.log\"\n"
FAKE_ESLINT_FAIL = "#!/bin/sh\necho \"  3:1  error  'x' is not defined  no-undef\"\nexit 1\n"
FAKE_ESLINT_OK = "#!/bin/sh\nexit 0\n"
FAKE_ESLINT_CONFIG_ERROR = "#!/bin/sh\necho 'Oops config' >&2\nexit 2\n"


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


if __name__ == "__main__":
    unittest.main()
