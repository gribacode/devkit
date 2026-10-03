#!/usr/bin/env python3
"""UserPromptSubmit запоминает время старта ответа, Notification показывает уведомление macOS."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import enabled, notify_mac, project_title, read_input, run, session_state  # noqa: E402


def main() -> int:
    data = read_input()
    event = data.get("hook_event_name")
    if event == "UserPromptSubmit":
        with session_state(data.get("session_id", "")) as state:
            state["prompt_at"] = time.time()
        return 0
    if event == "Notification" and enabled("NOTIFY"):
        notify_mac(project_title(data.get("cwd")), data.get("message") or "Claude ждет ответа")
    return 0


if __name__ == "__main__":
    run(main)
