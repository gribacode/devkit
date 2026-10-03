#!/usr/bin/env python3
"""Пишет строку активности в ~/.claude/worklog/<дата>.activity.tsv для отчета за день.

Ничего не печатает в stdout, иначе текст попадет в контекст модели.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import cleanup_state, enabled, git_branch, read_input, repo_root, run, worklog_dir  # noqa: E402

HEADER = ["time", "event", "session", "repo", "branch", "topic"]
TOPIC_LIMIT = 200


def first_line(text: str) -> str:
    for line in text.splitlines():
        flat = " ".join(line.split())
        if flat:
            return flat[:TOPIC_LIMIT]
    return ""


def clean(value: str) -> str:
    return " ".join(str(value).split())


def main() -> int:
    if not enabled("ACTIVITY"):
        return 0
    data = read_input()
    event = data.get("hook_event_name", "")
    if event == "SessionStart":
        cleanup_state()
    cwd = data.get("cwd") or os.getcwd()
    repo = repo_root(cwd)
    branch = git_branch(repo)
    topic = first_line(data.get("prompt") or "")
    now = datetime.now().astimezone()
    folder = worklog_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, now.strftime("%Y-%m-%d") + ".activity.tsv")
    is_new = not os.path.exists(path)
    row = [now.strftime("%Y-%m-%dT%H:%M:%S%z"), event, data.get("session_id", ""), repo, branch, topic]
    with open(path, "a", encoding="utf-8") as f:
        if is_new:
            f.write("\t".join(HEADER) + "\n")
        f.write("\t".join(clean(v) for v in row) + "\n")
    return 0


if __name__ == "__main__":
    run(main)
