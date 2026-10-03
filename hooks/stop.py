#!/usr/bin/env python3
"""Stop. Проверяет типы в правленых .ts через tsc, при чистом результате шлет уведомление о готовности."""
import json
import os
import re
import subprocess
import sys
import time
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    enabled, find_bin, find_up, node_env, notify_mac, project_title, read_input, read_jsonc, run, session_state,
    shorten,
)

MIN_SECONDS_FOR_NOTIFY = 20
TSC_TIMEOUT = 90
MAX_ERRORS = 20
NOTIFY_LIMIT = 100
ERROR_RE = re.compile(r"^(?P<file>.+?)\(\d+,\d+\): error TS\d+:")


def tsconfigs_for(path: str) -> List[str]:
    config = find_up(os.path.dirname(path), ["tsconfig.json"])
    if not config:
        return []
    try:
        data = read_jsonc(config)
    except (OSError, ValueError):
        return [config]
    refs = data.get("references") or [] if isinstance(data, dict) else []
    # Solution-style конфиг сам ничего не проверяет, реальные проверки в references
    if refs and data.get("files") == [] and not data.get("include"):
        found = []
        for ref in refs:
            target = os.path.normpath(os.path.join(os.path.dirname(config), ref.get("path", "")))
            if os.path.isdir(target):
                target = os.path.join(target, "tsconfig.json")
            if os.path.isfile(target):
                found.append(target)
        return found or [config]
    return [config]


def type_errors(files: List[str]) -> List[str]:
    edited = {os.path.realpath(p) for p in files}
    groups: Dict[str, None] = {}
    for path in files:
        for config in tsconfigs_for(path):
            groups[config] = None
    env = node_env()
    errors: List[str] = []
    for config in groups:
        folder = os.path.dirname(config)
        tsc = find_bin(folder, "tsc")
        if not tsc:
            continue
        try:
            proc = subprocess.run([tsc, "--noEmit", "--pretty", "false", "-p", config], capture_output=True,
                                  text=True, timeout=TSC_TIMEOUT, env=env, cwd=folder)
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in proc.stdout.splitlines():
            match = ERROR_RE.match(line)
            if match and os.path.realpath(os.path.join(folder, match.group("file"))) in edited:
                if line not in errors:
                    errors.append(line)
    return errors


def last_assistant_text(transcript_path: str) -> str:
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
    with open(transcript_path, encoding="utf-8") as f:
        lines = f.readlines()
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        text = " ".join(t for t in texts if t.strip())
        if text:
            return text
    return ""


def main() -> int:
    data = read_input()
    session = data.get("session_id", "")
    with session_state(session) as state:
        edited = list(state.get("edited", []))
        prompt_at = state.get("prompt_at")
    ts_files = [p for p in edited if p.endswith((".ts", ".tsx")) and os.path.isfile(p)]
    if enabled("TSC") and not data.get("stop_hook_active") and ts_files:
        errors = type_errors(ts_files)
        if errors:
            reason = "tsc нашел ошибки типов в правленых файлах, почини их.\n" + "\n".join(errors[:MAX_ERRORS])
            print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
            return 0
    with session_state(session) as state:
        state["edited"] = []
    if enabled("NOTIFY") and prompt_at and time.time() - float(prompt_at) >= MIN_SECONDS_FOR_NOTIFY:
        text = data.get("last_assistant_message") or last_assistant_text(data.get("transcript_path", "")) or "Готово"
        notify_mac(project_title(data.get("cwd")), shorten(text, NOTIFY_LIMIT))
    return 0


if __name__ == "__main__":
    run(main)
