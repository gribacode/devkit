import json
import os
import subprocess
import sys
import unittest

from tests.helpers import SCRIPTS, HookTestCase

sys.path.insert(0, SCRIPTS)
from worklog_blocks import compute  # noqa: E402

DAY = "2026-10-03"
HEADER = "time\tevent\tsession\trepo\tbranch\ttopic\n"


def row(hhmm: str, event: str, session: str = "s1", repo: str = "/r/front", branch: str = "feature/DEV-1",
        topic: str = "") -> str:
    return "%sT%s:00+0300\t%s\t%s\t%s\t%s\t%s\n" % (DAY, hhmm, event, session, repo, branch, topic)


class WorklogBlocksTest(HookTestCase):
    def activity(self, *rows: str) -> None:
        self.write("wl/%s.activity.tsv" % DAY, HEADER + "".join(rows))

    def blocks(self) -> list:
        return [(b["start"], b["end"], b["kind"], b["task"] or b["title"])
                for b in compute(DAY, os.path.join(self.home, "wl"))["blocks"]]

    def test_short_pause_is_work_long_pause_is_break(self) -> None:
        self.activity(
            row("09:00", "UserPromptSubmit", topic="Почини счетчик"), row("09:20", "Stop"),
            row("09:30", "UserPromptSubmit"), row("10:00", "Stop"),
            row("10:40", "UserPromptSubmit", repo="/x/calendar-app", branch="main"), row("11:00", "Stop", repo="/x/calendar-app", branch="main"),
        )
        self.assertEqual(self.blocks(), [("09:00", "10:00", "work", "DEV-1"), ("10:40", "11:00", "work", "calendar-app")])
        result = compute(DAY, os.path.join(self.home, "wl"))
        self.assertEqual(result["total_minutes"], 80)
        self.assertEqual(result["blocks"][0]["topics"], ["Почини счетчик"])
        self.assertFalse(result["has_journal"])

    def test_call_from_journal_overrides_activity(self) -> None:
        self.activity(row("10:00", "UserPromptSubmit"), row("12:00", "Stop"))
        self.write("wl/%s.md" % DAY, "# %s\n\n- 11:00-11:30 (30м) [call] дейлик\n- 10:00-11:00 (1h 0m) [dev] собрал фильтр\n" % DAY)
        self.assertEqual(self.blocks(), [("10:00", "11:00", "work", "DEV-1"), ("11:00", "11:30", "call", "дейлик"),
                                         ("11:30", "12:00", "work", "DEV-1")])
        result = compute(DAY, os.path.join(self.home, "wl"))
        self.assertTrue(result["has_journal"])
        self.assertEqual(result["blocks"][0]["notes"], ["собрал фильтр"])

    def test_short_block_is_absorbed_and_neighbors_merge(self) -> None:
        self.activity(
            row("09:00", "UserPromptSubmit"), row("09:40", "Stop"),
            row("09:40", "UserPromptSubmit", branch="feature/DEV-2"), row("09:45", "Stop", branch="feature/DEV-2"),
            row("09:45", "UserPromptSubmit"), row("10:30", "Stop"),
        )
        self.assertEqual(self.blocks(), [("09:00", "10:30", "work", "DEV-1")])

    def test_parallel_sessions_do_not_double_count(self) -> None:
        self.activity(
            row("09:00", "UserPromptSubmit", session="a"),
            row("09:30", "UserPromptSubmit", session="b", branch="feature/DEV-2"),
            row("10:00", "Stop", session="a"),
            row("10:30", "Stop", session="b", branch="feature/DEV-2"),
        )
        result = compute(DAY, os.path.join(self.home, "wl"))
        self.assertEqual(self.blocks(), [("09:00", "09:30", "work", "DEV-1"), ("09:30", "10:30", "work", "DEV-2")])
        self.assertEqual(result["total_minutes"], 90)

    def test_rounds_to_five_minutes(self) -> None:
        self.activity(row("09:02", "UserPromptSubmit"), row("09:48", "Stop"))
        self.assertEqual(self.blocks(), [("09:00", "09:50", "work", "DEV-1")])

    def test_prompt_without_stop_counts_five_minutes(self) -> None:
        self.activity(row("09:00", "UserPromptSubmit"))
        self.assertEqual(self.blocks(), [("09:00", "09:05", "work", "DEV-1")])

    def test_old_timeline_format(self) -> None:
        self.write("wl/%s.timeline.tsv" % DAY, "".join([
            "%sT09:00:00+0300\tUserPromptSubmit\t/u/frontend\tfeature/DEV-5\tfeature/DEV-9\tфронт\n" % DAY,
            "%sT09:30:00+0300\tStop\t/u/frontend\tfeature/DEV-5\tfeature/DEV-9\t\n" % DAY,
            "%sT10:00:00+0300\tUserPromptSubmit\t/u/frontend/imot.io\tfeature/DEV-5\tfeature/DEV-9\tбэк\n" % DAY,
            "%sT10:30:00+0300\tStop\t/u/frontend/imot.io\tfeature/DEV-5\tfeature/DEV-9\t\n" % DAY,
        ]))
        self.assertEqual(self.blocks(), [("09:00", "09:30", "work", "DEV-5"), ("10:00", "10:30", "work", "DEV-9")])

    def test_blocked_stop_extends_to_last_stop(self) -> None:
        self.activity(row("11:00", "UserPromptSubmit"), row("11:05", "Stop"), row("11:30", "Stop"))
        self.assertEqual(self.blocks(), [("11:00", "11:30", "work", "DEV-1")])

    def test_topics_follow_block_task_and_overlap(self) -> None:
        self.activity(
            row("09:00", "UserPromptSubmit", session="a", branch="feature/ABC-1", topic="a1"),
            row("09:05", "UserPromptSubmit", session="b", branch="feature/ABC-2", topic="b1"),
            row("09:40", "Stop", session="b", branch="feature/ABC-2"),
            row("10:30", "Stop", session="a", branch="feature/ABC-1"),
        )
        self.write("wl/%s.md" % DAY, "- 09:20-09:30 (10м) [call] созвон\n")
        result = compute(DAY, os.path.join(self.home, "wl"))
        got = [(b["start"], b["task"] or b["title"], b["topics"]) for b in result["blocks"]]
        self.assertEqual(got, [("09:00", "ABC-2", ["b1"]), ("09:20", "созвон", []), ("09:30", "ABC-2", ["b1"]),
                               ("09:40", "ABC-1", ["a1"])])

    def test_empty_day(self) -> None:
        os.makedirs(os.path.join(self.home, "wl"))
        result = compute(DAY, os.path.join(self.home, "wl"))
        self.assertEqual((result["blocks"], result["total_minutes"]), ([], 0))

    def test_cli_prints_json(self) -> None:
        self.activity(row("09:00", "UserPromptSubmit"), row("09:30", "Stop"))
        out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "worklog_blocks.py"), DAY, "--dir",
                              os.path.join(self.home, "wl")], capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out)["total_minutes"], 30)


if __name__ == "__main__":
    unittest.main()
