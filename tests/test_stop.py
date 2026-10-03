import json
import os
import sys
import time
import unittest

from tests.helpers import HOOKS, HookTestCase

sys.path.insert(0, HOOKS)
import stop  # noqa: E402

FAKE_TSC = """#!/bin/sh
echo "src/a.ts(3,7): error TS2322: Type 'string' is not assignable to type 'number'."
echo "src/old.ts(1,1): error TS2304: Cannot find name 'legacy'."
exit 2
"""

FAKE_PYRIGHT = """#!/bin/sh
echo "$PWD/app/a.py"
echo "  $PWD/app/a.py:3:5 - error: Type \\"str\\" is not assignable to \\"int\\""
echo "  $PWD/app/old.py:1:1 - error: legacy"
echo "2 errors"
exit 1
"""
FAKE_MYPY = """#!/bin/sh
echo "app/a.py:3: error: Incompatible types in assignment  [assignment]"
echo "app/dep.py:9: error: imported module problem  [misc]"
exit 1
"""

FAKE_TEST_RUNNER = "#!/bin/sh\necho \"$(basename \"$0\") $@\" >> \"%s/tests.log\"\necho 'FAIL  src/a.test.ts > sums'\nexit %d\n"


class StopTest(HookTestCase):
    def set_state(self, **state) -> None:
        self.write(".claude/devkit/state/s1.json", json.dumps(state))

    def state(self) -> dict:
        with open(os.path.join(self.home, ".claude/devkit/state/s1.json")) as f:
            return json.load(f)

    def ts_project(self) -> str:
        self.write("proj/tsconfig.json", '{ "include": ["src"], }  // jsonc\n')
        self.write("proj/node_modules/.bin/tsc", FAKE_TSC, executable=True)
        self.write("proj/src/old.ts", "legacy\n")
        return os.path.realpath(self.write("proj/src/a.ts", "const a: number = 'x'\n"))

    def payload(self, **extra) -> dict:
        data = {"hook_event_name": "Stop", "session_id": "s1", "cwd": os.path.join(self.home, "proj")}
        data.update(extra)
        return data

    def test_blocks_on_errors_in_edited_files_only(self) -> None:
        path = self.ts_project()
        self.set_state(edited=[path], prompt_at=time.time() - 60)
        code, out, err = self.run_hook("stop.py", self.payload())
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["decision"], "block")
        self.assertIn("TS2322", result["reason"])
        self.assertNotIn("old.ts", result["reason"])
        self.assertNotIn("NOTIFY", err)
        self.assertEqual(self.state()["edited"], [path])

    def test_stop_hook_active_skips_tsc_but_notifies_and_clears(self) -> None:
        path = self.ts_project()
        self.set_state(edited=[path], prompt_at=time.time() - 60)
        code, out, err = self.run_hook("stop.py", self.payload(stop_hook_active=True))
        self.assertEqual((code, out), (0, ""))
        self.assertIn("NOTIFY|", err)
        self.assertEqual(self.state()["edited"], [])

    def test_clean_run_notifies_with_last_message(self) -> None:
        transcript = self.write("t.jsonl", "\n".join([
            json.dumps({"type": "user", "message": {"content": "hi"}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Готово, поправил   счетчик"}]}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}}),
        ]) + "\n")
        self.set_state(edited=[], prompt_at=time.time() - 30)
        code, out, err = self.run_hook("stop.py", self.payload(transcript_path=transcript))
        self.assertEqual((code, out), (0, ""))
        self.assertIn("|Готово, поправил счетчик", err)

    def test_fast_answer_does_not_notify(self) -> None:
        self.set_state(edited=[], prompt_at=time.time())
        _, _, err = self.run_hook("stop.py", self.payload())
        self.assertNotIn("NOTIFY", err)

    def test_tsc_switch_off(self) -> None:
        path = self.ts_project()
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload(), env={"DEVKIT_TSC": "0"})
        self.assertEqual((code, out), (0, ""))

    def test_tsconfigs_for_follows_solution_references(self) -> None:
        self.write("vite/tsconfig.json", '{ "files": [], "references": [{ "path": "./tsconfig.app.json" }, { "path": "./tsconfig.node.json" },], }')
        self.write("vite/tsconfig.app.json", '{ "include": ["src"] }')
        self.write("vite/tsconfig.node.json", '{ "include": ["vite.config.ts"] }')
        path = self.write("vite/src/main.tsx", "x\n")
        configs = stop.tsconfigs_for(path)
        self.assertEqual([os.path.basename(c) for c in configs], ["tsconfig.app.json", "tsconfig.node.json"])

    def test_tsconfigs_for_plain(self) -> None:
        path = self.ts_project()
        self.assertEqual(stop.tsconfigs_for(path), [os.path.join(self.home, "proj", "tsconfig.json")])

    def py_project(self, checker: str, script: str) -> str:
        section = "[tool.pyright]\n" if checker == "pyright" else "[tool.mypy]\n"
        self.write("py/pyproject.toml", section)
        self.write("py/.venv/bin/" + checker, script, executable=True)
        self.write("py/app/old.py", "x\n")
        return os.path.realpath(self.write("py/app/a.py", "x: int = 'a'\n"))

    def test_pyright_blocks_on_edited_file_only(self) -> None:
        path = self.py_project("pyright", FAKE_PYRIGHT)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload())
        result = json.loads(out)
        self.assertEqual(result["decision"], "block")
        self.assertIn("a.py:3:5", result["reason"])
        self.assertNotIn("old.py", result["reason"])

    def test_mypy_filters_imported_modules(self) -> None:
        path = self.py_project("mypy", FAKE_MYPY)
        self.set_state(edited=[path], prompt_at=time.time())
        _, out, _ = self.run_hook("stop.py", self.payload())
        reason = json.loads(out)["reason"]
        self.assertIn("app/a.py:3", reason)
        self.assertNotIn("dep.py", reason)

    def test_types_switch_off(self) -> None:
        path = self.py_project("pyright", FAKE_PYRIGHT)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload(), env={"DEVKIT_TYPES": "0"})
        self.assertEqual((code, out), (0, ""))

    def test_python_without_typechecker_config_is_silent(self) -> None:
        self.write("py/.venv/bin/pyright", FAKE_PYRIGHT, executable=True)
        path = os.path.realpath(self.write("py/app/a.py", "x\n"))
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload())
        self.assertEqual((code, out), (0, ""))

    def runner(self, rel: str, code: int) -> None:
        self.write(rel, FAKE_TEST_RUNNER % (self.home, code), executable=True)

    def tests_log(self) -> str:
        path = os.path.join(self.home, "tests.log")
        return open(path).read() if os.path.exists(path) else ""

    def js_project(self) -> str:
        self.write("web/package.json", "{}")
        return os.path.realpath(self.write("web/src/a.js", "x\n"))

    def test_tests_do_not_run_without_opt_in(self) -> None:
        path = self.js_project()
        self.runner("web/node_modules/.bin/vitest", 1)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload())
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(self.tests_log(), "")

    def test_vitest_related_failure_blocks(self) -> None:
        path = self.js_project()
        self.runner("web/node_modules/.bin/vitest", 1)
        self.set_state(edited=[path], prompt_at=time.time())
        _, out, _ = self.run_hook("stop.py", self.payload(), env={"DEVKIT_TESTS": "1"})
        result = json.loads(out)
        self.assertIn("FAIL", result["reason"])
        self.assertIn("vitest related --run --passWithNoTests %s" % path, self.tests_log())

    def test_jest_used_without_vitest(self) -> None:
        path = self.js_project()
        self.runner("web/node_modules/.bin/jest", 0)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload(), env={"DEVKIT_TESTS": "1"})
        self.assertEqual((code, out), (0, ""))
        self.assertIn("jest --findRelatedTests %s --passWithNoTests" % path, self.tests_log())

    def test_pytest_runs_matching_test_file_and_ignores_no_tests(self) -> None:
        self.write("py/pyproject.toml", "")
        path = os.path.realpath(self.write("py/app/calc.py", "x\n"))
        test = os.path.realpath(self.write("py/tests/test_calc.py", "x\n"))
        self.write("py/.venv/lib/test_calc.py", "x\n")
        self.runner("py/.venv/bin/pytest", 5)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload(), env={"DEVKIT_TESTS": "1"})
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(self.tests_log().strip(), "pytest -q %s" % test)

    def test_python_tests_finds_edited_tests_directly(self) -> None:
        root = os.path.join(self.home, "py")
        edited = os.path.realpath(self.write("py/tests/test_x.py", "x\n"))
        self.assertEqual(stop.python_tests(root, [edited]), [edited])


    def test_unresolved_imports_do_not_block(self) -> None:
        script = (
            "#!/bin/sh\n"
            "echo \"  $PWD/app/a.py:1:8 - error: Import \\\"fastapi\\\" could not be resolved (reportMissingImports)\"\n"
            "exit 1\n"
        )
        path = self.py_project("pyright", script)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload())
        self.assertEqual((code, out), (0, ""))

    def test_mypy_missing_stubs_do_not_block(self) -> None:
        script = "#!/bin/sh\necho 'app/a.py:1: error: Cannot find implementation or library stub for module named \"x\"  [import-not-found]'\nexit 1\n"
        path = self.py_project("mypy", script)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload())
        self.assertEqual((code, out), (0, ""))

    def test_pytest_collection_and_usage_errors_do_not_block(self) -> None:
        self.write("py/pyproject.toml", "")
        path = os.path.realpath(self.write("py/app/calc.py", "x\n"))
        self.write("py/tests/test_calc.py", "x\n")
        for code in (2, 4):
            self.runner("py/.venv/bin/pytest", code)
            self.set_state(edited=[path], prompt_at=time.time())
            result = self.run_hook("stop.py", self.payload(), env={"DEVKIT_TESTS": "1"})
            self.assertEqual(result[:2], (0, ""), code)


    def test_expired_budget_skips_remaining_checks(self) -> None:
        path = self.ts_project()
        self.write("proj/node_modules/.bin/tsc", "#!/bin/sh\ntouch \"%s/tsc_ran\"\nexit 2\n" % self.home, executable=True)
        self.assertEqual(stop.first_failure([path], deadline=time.time()), "")
        self.assertFalse(os.path.exists(os.path.join(self.home, "tsc_ran")))

    def test_timeout_shrinks_to_remaining_budget(self) -> None:
        now = time.time()
        self.assertEqual(stop.step_timeout(now + 1000), 90)
        self.assertEqual(stop.step_timeout(now + 30.5), 30)
        self.assertIsNone(stop.step_timeout(now + 3))


if __name__ == "__main__":
    unittest.main()
