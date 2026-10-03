import glob
import os
import subprocess
import unittest

from tests.helpers import HookTestCase


class ActivityTest(HookTestCase):
    def rows(self) -> list:
        files = glob.glob(os.path.join(self.home, ".claude/worklog/*.activity.tsv"))
        self.assertEqual(len(files), 1)
        with open(files[0], encoding="utf-8") as f:
            return [line.rstrip("\n").split("\t") for line in f]

    def test_writes_header_and_prompt_row_in_git_repo(self) -> None:
        repo = os.path.join(self.home, "proj")
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q", "-b", "feature/DEV-7", repo], check=True)
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "cwd": repo,
            "prompt": "\n  Почини\tсчетчик\nвторая строка",
        }
        code, out, err = self.run_hook("activity.py", payload)
        self.assertEqual((code, out), (0, ""))
        rows = self.rows()
        self.assertEqual(rows[0], ["time", "event", "session", "repo", "branch", "topic"])
        self.assertEqual(rows[1][1:], ["UserPromptSubmit", "s1", repo, "feature/DEV-7", "Почини счетчик"])

    def test_outside_git_has_empty_repo(self) -> None:
        self.run_hook("activity.py", {"hook_event_name": "Stop", "session_id": "s1", "cwd": self.home})
        self.assertEqual(self.rows()[1][1:], ["Stop", "s1", "", "", ""])

    def test_topic_is_truncated_to_200(self) -> None:
        self.run_hook("activity.py", {"hook_event_name": "UserPromptSubmit", "cwd": self.home, "prompt": "я" * 500})
        self.assertEqual(len(self.rows()[1][5]), 200)

    def test_switch_off(self) -> None:
        self.run_hook("activity.py", {"hook_event_name": "Stop", "cwd": self.home}, env={"DEVKIT_ACTIVITY": "0"})
        self.assertEqual(glob.glob(os.path.join(self.home, ".claude/worklog/*")), [])


if __name__ == "__main__":
    unittest.main()
