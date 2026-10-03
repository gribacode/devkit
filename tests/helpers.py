import json
import os
import subprocess
import sys
import tempfile
import unittest
from typing import Any, Dict, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")
SCRIPTS = os.path.join(ROOT, "scripts")


class HookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = os.path.realpath(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_hook(
        self,
        script: str,
        payload: Optional[Dict[str, Any]] = None,
        env: Optional[Dict[str, str]] = None,
        raw: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        full_env = dict(os.environ, HOME=self.home, DEVKIT_NOTIFY_DRYRUN="1")
        if env:
            full_env.update(env)
        stdin = raw if raw is not None else json.dumps(payload or {})
        proc = subprocess.run(
            [sys.executable, os.path.join(HOOKS, script)],
            input=stdin,
            capture_output=True,
            text=True,
            env=full_env,
            cwd=cwd or self.home,
            timeout=60,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def write(self, rel: str, content: str, executable: bool = False) -> str:
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if executable:
            os.chmod(path, 0o755)
        return path
