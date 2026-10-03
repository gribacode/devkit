import json
import os
import unittest

from tests.helpers import HookTestCase


class NotifyTest(HookTestCase):
    def test_prompt_records_start_time_silently(self) -> None:
        code, out, err = self.run_hook("notify.py", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
        self.assertEqual((code, out, err), (0, "", ""))
        with open(os.path.join(self.home, ".claude/devkit/state/s1.json")) as f:
            self.assertIn("prompt_at", json.load(f))

    def test_notification_event_notifies_with_project_title(self) -> None:
        proj = os.path.join(self.home, "calendar-app")
        os.makedirs(proj)
        payload = {"hook_event_name": "Notification", "session_id": "s1", "cwd": proj,
                   "message": "Claude needs your permission to use Bash"}
        code, _, err = self.run_hook("notify.py", payload)
        self.assertEqual(code, 0)
        self.assertIn("NOTIFY|calendar-app|Claude needs your permission to use Bash", err)

    def test_notification_switch_off(self) -> None:
        payload = {"hook_event_name": "Notification", "cwd": self.home, "message": "x"}
        _, _, err = self.run_hook("notify.py", payload, env={"DEVKIT_NOTIFY": "0"})
        self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()
