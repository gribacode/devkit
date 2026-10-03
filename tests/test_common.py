import json
import os
import sys
import time
import unittest
from unittest import mock

from tests.helpers import HOOKS, HookTestCase

sys.path.insert(0, HOOKS)
import _common  # noqa: E402


class CommonTest(HookTestCase):
    def setUp(self) -> None:
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"HOME": self.home})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_enabled_reads_env_switch(self) -> None:
        with mock.patch.dict(os.environ, {"DEVKIT_GUARD": "0"}):
            self.assertFalse(_common.enabled("GUARD"))
        self.assertTrue(_common.enabled("TSC"))

    def test_session_state_persists_between_calls(self) -> None:
        with _common.session_state("abc") as st:
            st["prompt_at"] = 1.5
        with _common.session_state("abc") as st:
            self.assertEqual(st["prompt_at"], 1.5)

    def test_session_state_survives_corrupted_file(self) -> None:
        path = _common.state_path("bad")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("{not json")
        with _common.session_state("bad") as st:
            self.assertEqual(st, {})

    def test_cleanup_state_removes_old_files(self) -> None:
        with _common.session_state("old") as st:
            st["x"] = 1
        path = _common.state_path("old")
        past = time.time() - 8 * 24 * 3600
        os.utime(path, (past, past))
        _common.cleanup_state()
        self.assertFalse(os.path.exists(path))

    def test_find_bin_walks_up(self) -> None:
        tool = self.write("proj/node_modules/.bin/tsc", "#!/bin/sh\n", executable=True)
        os.makedirs(os.path.join(self.home, "proj/apps/web/src"))
        found = _common.find_bin(os.path.join(self.home, "proj/apps/web/src"), "tsc")
        self.assertEqual(found, tool)

    def test_node_env_adds_fnm_fallback_when_node_missing(self) -> None:
        fnm_bin = os.path.join(self.home, "fnm/aliases/default/bin")
        os.makedirs(fnm_bin)
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin:/bin", "FNM_DIR": os.path.join(self.home, "fnm")}):
            env = _common.node_env()
        self.assertTrue(env["PATH"].startswith(fnm_bin + os.pathsep))

    def test_is_secret_path(self) -> None:
        blocked = [".env", "app/.env.local", "certs/server.pem", "id_rsa", "credentials.prod.json", ".npmrc",
                   os.path.join(self.home, ".ssh/config"), os.path.join(self.home, ".aws/credentials")]
        allowed = [".env.example", ".env.sample", ".env.template", "src/env.ts", "id_rsa.pub", "README.md", ""]
        for p in blocked:
            self.assertTrue(_common.is_secret_path(p), p)
        for p in allowed:
            self.assertFalse(_common.is_secret_path(p), p)

    def test_read_jsonc_handles_comments_and_trailing_commas(self) -> None:
        path = self.write("tsconfig.json", """{
  "extends": "./base.json",  // комментарий
  /* блок */
  "exclude": ["./**/*.(test|spec).ts", "./dist",],
  "compilerOptions": {"paths": {"~a/*": ["./src/a/*"],},},
}
""")
        data = _common.read_jsonc(path)
        self.assertEqual(data["exclude"], ["./**/*.(test|spec).ts", "./dist"])
        self.assertEqual(data["compilerOptions"]["paths"]["~a/*"], ["./src/a/*"])

    def test_shorten(self) -> None:
        self.assertEqual(_common.shorten("a  b\nc", 10), "a b c")
        self.assertEqual(_common.shorten("x" * 20, 10), "x" * 9 + "…")


if __name__ == "__main__":
    unittest.main()
