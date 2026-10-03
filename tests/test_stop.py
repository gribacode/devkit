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


if __name__ == "__main__":
    unittest.main()
