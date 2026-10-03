import json
import os
import re
import unittest

from tests.helpers import HOOKS, ROOT, HookTestCase

SCRIPTS = ["activity.py", "notify.py", "stop.py", "guard_bash.py", "guard_secrets.py", "format_edit.py"]


class ManifestTest(unittest.TestCase):
    def test_hooks_json_references_existing_scripts(self) -> None:
        with open(os.path.join(HOOKS, "hooks.json")) as f:
            config = json.load(f)
        commands = [h["command"] for groups in config["hooks"].values() for g in groups for h in g["hooks"]]
        self.assertTrue(commands)
        for command in commands:
            match = re.search(r'\$\{CLAUDE_PLUGIN_ROOT\}/(hooks/[a-z_]+\.py)', command)
            self.assertIsNotNone(match, command)
            self.assertTrue(os.path.isfile(os.path.join(ROOT, match.group(1))), command)

    def test_expected_events_registered(self) -> None:
        with open(os.path.join(HOOKS, "hooks.json")) as f:
            events = set(json.load(f)["hooks"])
        self.assertEqual(events, {"SessionStart", "SessionEnd", "UserPromptSubmit", "Notification",
                                  "PreToolUse", "PostToolUse", "Stop"})

    def test_plugin_manifests_are_valid(self) -> None:
        for name in ("plugin.json", "marketplace.json"):
            with open(os.path.join(ROOT, ".claude-plugin", name)) as f:
                self.assertEqual(json.load(f)["name"], "devkit")


class BrokenInputTest(HookTestCase):
    def test_every_hook_survives_garbage_and_empty_stdin(self) -> None:
        for script in SCRIPTS:
            for raw in ("", "{not json", "[1,2]"):
                code, out, _ = self.run_hook(script, raw=raw)
                self.assertEqual(code, 0, "%s %r" % (script, raw))
                self.assertEqual(out, "", "%s %r" % (script, raw))


if __name__ == "__main__":
    unittest.main()
