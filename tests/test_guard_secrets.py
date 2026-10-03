import unittest

from tests.helpers import HookTestCase


def payload(tool: str, **tool_input: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}


class GuardSecretsTest(HookTestCase):
    def test_blocks_env_read(self) -> None:
        code, _, err = self.run_hook("guard_secrets.py", payload("Read", file_path="/p/.env"))
        self.assertEqual(code, 2)
        self.assertIn(".env", err)

    def test_blocks_env_local_edit_and_key(self) -> None:
        for p in ("/p/.env.local", "/p/id_rsa"):
            code, _, _ = self.run_hook("guard_secrets.py", payload("Edit", file_path=p))
            self.assertEqual(code, 2, p)

    def test_blocks_grep_path(self) -> None:
        code, _, _ = self.run_hook("guard_secrets.py", payload("Grep", pattern="KEY", path="/p/.env.production"))
        self.assertEqual(code, 2)

    def test_allows_example_and_source(self) -> None:
        for p in ("/p/.env.example", "/p/src/env.ts"):
            code, _, err = self.run_hook("guard_secrets.py", payload("Read", file_path=p))
            self.assertEqual((code, err), (0, ""), p)

    def test_switch_off(self) -> None:
        code, _, _ = self.run_hook("guard_secrets.py", payload("Read", file_path="/p/.env"), env={"DEVKIT_GUARD": "0"})
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
