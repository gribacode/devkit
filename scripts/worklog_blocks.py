#!/usr/bin/env python3
"""Считает блоки рабочего времени за день из ~/.claude/worklog и печатает JSON для команды /report.

Каждая минута дня принадлежит задаче последнего начатого промпта, созвоны из журнала перекрывают
активность. Паузы до 15 минут считаются работой, блоки короче 10 минут склеиваются с соседом,
границы округляются до 5 минут.
"""
import argparse
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

GAP_MINUTES = 15
MIN_BLOCK_MINUTES = 10
ROUND_MINUTES = 5
OPEN_SEGMENT_SECONDS = 5 * 60
DAY_MINUTES = 24 * 60
TASK_RE = re.compile(r"[A-Z][A-Z0-9]+-\d+")
JOURNAL_RE = re.compile(r"^- (\d{2}):(\d{2})-(\d{2}):(\d{2}) \([^)]*\) \[(\w+)\] (.*)$")
CALL_TAGS = {"call", "meeting", "talk"}

Event = Dict[str, Any]
Key = Tuple[str, str]


def _second(stamp: str) -> Optional[int]:
    try:
        moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None
    return moment.hour * 3600 + moment.minute * 60 + moment.second


def _read_rows(path: str) -> List[List[str]]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [line.rstrip("\n").split("\t") for line in f if line.strip()]


def load_events(day: str, folder: str) -> List[Event]:
    events: List[Event] = []
    for cols in _read_rows(os.path.join(folder, day + ".activity.tsv")):
        if cols[0] == "time" or len(cols) < 6:
            continue
        second = _second(cols[0])
        if second is not None:
            events.append({"second": second, "event": cols[1], "session": cols[2], "repo": cols[3],
                           "branch": cols[4], "topic": cols[5]})
    for cols in _read_rows(os.path.join(folder, day + ".timeline.tsv")):
        if len(cols) < 6:
            continue
        second = _second(cols[0])
        if second is None:
            continue
        # Старый хук писал ветку фронта и ветку вложенного imot.io в разные колонки
        branch = cols[4] if os.sep + "imot.io" in cols[2] else cols[3]
        events.append({"second": second, "event": cols[1], "session": "legacy", "repo": cols[2],
                       "branch": branch, "topic": cols[5]})
    events.sort(key=lambda e: e["second"])
    return events


def task_of(repo: str, branch: str) -> str:
    match = TASK_RE.search(branch or "")
    if match:
        return match.group(0)
    return os.path.basename(repo.rstrip("/")) if repo else "без репозитория"


def segments(events: List[Event]) -> List[Event]:
    by_session: Dict[str, List[Event]] = {}
    for event in events:
        by_session.setdefault(event["session"], []).append(event)
    result: List[Event] = []
    for items in by_session.values():
        for i, event in enumerate(items):
            if event["event"] != "UserPromptSubmit":
                continue
            # Stop может быть заблокирован хуком, тогда работа идет до последнего Stop перед следующим промптом
            end = None
            for nxt in items[i + 1:]:
                if nxt["event"] == "UserPromptSubmit":
                    end = nxt["second"] if end is None else end
                    break
                if nxt["event"] in ("Stop", "SessionEnd"):
                    end = nxt["second"]
            if end is None:
                end = event["second"] + OPEN_SEGMENT_SECONDS
            result.append(dict(event, end=max(end, event["second"] + 60), task=task_of(event["repo"], event["branch"])))
    result.sort(key=lambda s: s["second"])
    return result


def load_journal(day: str, folder: str) -> Tuple[bool, List[Dict[str, Any]]]:
    path = os.path.join(folder, day + ".md")
    if not os.path.isfile(path):
        return False, []
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            match = JOURNAL_RE.match(line.strip())
            if not match:
                continue
            h1, m1, h2, m2, tag, text = match.groups()
            entries.append({"start": int(h1) * 60 + int(m1), "end": int(h2) * 60 + int(m2), "tag": tag, "text": text})
    return True, entries


def _runs(owners: List[Optional[Key]]) -> List[List[Any]]:
    runs: List[List[Any]] = []
    for minute, key in enumerate(owners):
        if key is None:
            continue
        if runs and runs[-1][2] == key and runs[-1][1] == minute:
            runs[-1][1] = minute + 1
        else:
            runs.append([minute, minute + 1, key])
    return runs


def _merge_equal(runs: List[List[Any]]) -> List[List[Any]]:
    merged: List[List[Any]] = []
    for run in runs:
        if merged and merged[-1][2] == run[2] and merged[-1][1] == run[0]:
            merged[-1][1] = run[1]
        else:
            merged.append(list(run))
    return merged


def _absorb_short(runs: List[List[Any]]) -> List[List[Any]]:
    changed = True
    while changed:
        changed = False
        for i, run in enumerate(runs):
            if run[2][0] != "work" or run[1] - run[0] >= MIN_BLOCK_MINUTES:
                continue
            prev = runs[i - 1] if i > 0 and runs[i - 1][1] == run[0] and runs[i - 1][2][0] == "work" else None
            nxt = runs[i + 1] if i + 1 < len(runs) and runs[i + 1][0] == run[1] and runs[i + 1][2][0] == "work" else None
            target = prev or nxt
            if target is None:
                continue
            target[0], target[1] = min(target[0], run[0]), max(target[1], run[1])
            del runs[i]
            runs[:] = _merge_equal(runs)
            changed = True
            break
    return runs


def _round(minute: int) -> int:
    return int(round(minute / float(ROUND_MINUTES))) * ROUND_MINUTES


def _hhmm(minute: int) -> str:
    return "%02d:%02d" % divmod(min(minute, DAY_MINUTES - 1), 60)


def compute(day: str, folder: str) -> Dict[str, Any]:
    segs = segments(load_events(day, folder))
    has_journal, journal = load_journal(day, folder)
    calls = [e for e in journal if e["tag"] in CALL_TAGS]
    notes = [e for e in journal if e["tag"] not in CALL_TAGS]

    owners: List[Optional[Key]] = [None] * DAY_MINUTES
    for seg in segs:
        for minute in range(seg["second"] // 60, min(DAY_MINUTES, -(-seg["end"] // 60))):
            owners[minute] = ("work", seg["task"])
    for index, call in enumerate(calls):
        for minute in range(call["start"], min(DAY_MINUTES, call["end"])):
            owners[minute] = ("call", str(index))

    runs = _runs(owners)
    for prev, nxt in zip(runs, runs[1:]):
        if 0 < nxt[0] - prev[1] <= GAP_MINUTES:
            prev[1] = nxt[0]
    runs = _absorb_short(_merge_equal(runs))

    blocks = []
    for start, end, key in runs:
        r_start, r_end = _round(start), _round(end)
        if r_end <= r_start:
            continue
        inside = [s for s in segs if s["second"] < end * 60 and s["end"] > start * 60 and s["task"] == key[1]]
        block = {"start": _hhmm(r_start), "end": _hhmm(r_end), "minutes": r_end - r_start, "kind": key[0],
                 "task": key[1] if key[0] == "work" else "", "title": "", "topics": [], "notes": [],
                 "repos": [], "branches": []}
        if key[0] == "call":
            block["title"] = calls[int(key[1])]["text"]
        else:
            for seg in inside:
                for field, value in (("topics", seg["topic"]), ("repos", seg["repo"]), ("branches", seg["branch"])):
                    if value and value not in block[field]:
                        block[field].append(value)
            block["notes"] = [n["text"] for n in notes if n["start"] < end and n["end"] > start]
        blocks.append(block)

    repos: List[str] = []
    for seg in segs:
        if seg["repo"] and seg["repo"] not in repos:
            repos.append(seg["repo"])
    return {"date": day, "has_journal": has_journal, "total_minutes": sum(b["minutes"] for b in blocks),
            "repos": repos, "blocks": blocks}


def resolve_day(value: Optional[str]) -> str:
    today = datetime.now().date()
    if not value or value == "сегодня":
        return today.isoformat()
    if value == "вчера":
        return (today - timedelta(days=1)).isoformat()
    return datetime.strptime(value, "%Y-%m-%d").date().isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Блоки рабочего времени за день")
    parser.add_argument("day", nargs="?", default="")
    parser.add_argument("--dir", default=os.path.join(os.path.expanduser("~"), ".claude", "worklog"))
    args = parser.parse_args()
    print(json.dumps(compute(resolve_day(args.day), args.dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
