#!/usr/bin/env python3
"""Stop. Проверяет типы правленых .ts и .py, по флагу гоняет связанные тесты, при чистом результате шлет уведомление."""
import json
import os
import re
import subprocess
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    enabled, find_bin, find_up, node_env, notify_mac, opted_in, project_title, read_input, read_jsonc, run,
    session_state, shorten,
)
from _stacks import PY_ROOT_MARKERS, python_bin, python_root, python_typechecker  # noqa: E402

MIN_SECONDS_FOR_NOTIFY = 20
# Общий бюджет Stop меньше таймаута хука в hooks.json, чтобы хук успел очистить состояние
STOP_BUDGET = 220
STEP_TIMEOUT = 90
MIN_STEP_SECONDS = 5
MAX_ERRORS = 20
NOTIFY_LIMIT = 100
ERROR_RE = re.compile(r"^(?P<file>.+?)\(\d+,\d+\): error TS\d+:")
MAX_TEST_LINES = 30
JS_TEST_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
WALK_SKIP = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
PY_ERROR_RES = (
    re.compile(r"^\s*(?P<file>.+?\.pyi?):\d+:\d+ - error:"),  # pyright
    re.compile(r"^(?P<file>.+?\.pyi?):\d+(?::\d+)?: error:"),  # mypy
)
# Неразрешенный импорт это окружение (нет venv, пакет не стоит), а не ошибка правки
PY_IMPORT_NOISE = ("reportMissingImports", "reportMissingModuleSource", "[import-not-found]", "[import-untyped]")


def step_timeout(deadline: float) -> Optional[int]:
    remaining = deadline - time.time()
    return None if remaining < MIN_STEP_SECONDS else int(min(STEP_TIMEOUT, remaining))


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


def type_errors(files: List[str], deadline: float) -> List[str]:
    edited = {os.path.realpath(p) for p in files}
    groups: Dict[str, None] = {}
    for path in files:
        for config in tsconfigs_for(path):
            groups[config] = None
    env = node_env()
    errors: List[str] = []
    for config in groups:
        folder = os.path.dirname(config)
        tsc, timeout = find_bin(folder, "tsc"), step_timeout(deadline)
        if timeout is None:
            break
        if not tsc:
            continue
        try:
            proc = subprocess.run([tsc, "--noEmit", "--pretty", "false", "-p", config], capture_output=True,
                                  text=True, timeout=timeout, env=env, cwd=folder)
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in proc.stdout.splitlines():
            match = ERROR_RE.match(line)
            if match and os.path.realpath(os.path.join(folder, match.group("file"))) in edited:
                if line not in errors:
                    errors.append(line)
    return errors


def python_type_errors(files: List[str], deadline: float) -> List[str]:
    edited = {os.path.realpath(p) for p in files}
    groups: Dict[Tuple[str, str], List[str]] = {}
    for path in files:
        checker = python_typechecker(path)
        if checker:
            groups.setdefault((python_root(path), checker), []).append(path)
    env = node_env()
    errors: List[str] = []
    for (root, checker), group in groups.items():
        binary, timeout = python_bin(group[0], checker), step_timeout(deadline)
        if timeout is None:
            break
        if not binary:
            continue
        try:
            proc = subprocess.run([binary] + group, capture_output=True, text=True, timeout=timeout, env=env,
                                  cwd=root)
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in proc.stdout.splitlines():
            if any(noise in line for noise in PY_IMPORT_NOISE):
                continue
            for regex in PY_ERROR_RES:
                match = regex.match(line)
                if not match:
                    continue
                # mypy заходит в импортируемые модули, оставляем только правленые файлы
                if os.path.realpath(os.path.join(root, match.group("file"))) in edited and line.strip() not in errors:
                    errors.append(line.strip())
                break
    return errors


def group_by_root(files: List[str], markers: List[str]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for path in files:
        marker = find_up(os.path.dirname(path), markers)
        groups.setdefault(os.path.dirname(marker) if marker else os.path.dirname(path), []).append(path)
    return groups


def python_tests(root: str, files: List[str]) -> List[str]:
    found: List[str] = []
    wanted = set()
    for path in files:
        name = os.path.basename(path)
        if name.startswith("test_") or name.endswith("_test.py"):
            found.append(path)
        else:
            wanted.add("test_" + name)
    if wanted:
        for folder, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in WALK_SKIP and not d.startswith(".")]
            found.extend(os.path.join(folder, n) for n in names if n in wanted)
    return sorted(set(found))


def run_tests(cmd: List[str], cwd: str, fail_codes: Optional[Set[int]], deadline: float) -> str:
    # fail_codes None значит любой ненулевой код
    timeout = step_timeout(deadline)
    if timeout is None:
        return ""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=node_env(), cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    failed = proc.returncode != 0 if fail_codes is None else proc.returncode in fail_codes
    if not failed:
        return ""
    lines = [line for line in (proc.stdout + "\n" + proc.stderr).splitlines() if line.strip()]
    return "\n".join(lines[-MAX_TEST_LINES:])


def related_test_failures(files: List[str], deadline: float) -> str:
    failures: List[str] = []
    for root, group in group_by_root([p for p in files if p.endswith(JS_TEST_EXT)], ["package.json"]).items():
        vitest, jest = find_bin(root, "vitest"), find_bin(root, "jest")
        if vitest:
            failures.append(run_tests([vitest, "related", "--run", "--passWithNoTests"] + group, root, None, deadline))
        elif jest:
            failures.append(run_tests([jest, "--findRelatedTests"] + group + ["--passWithNoTests"], root, None, deadline))
    for root, group in group_by_root([p for p in files if p.endswith(".py")], PY_ROOT_MARKERS).items():
        pytest, tests = python_bin(group[0], "pytest"), python_tests(root, group)
        if pytest and tests:
            # Падение тестов у pytest это код 1. Коды 2 до 5 это сбор, конфиг или отсутствие тестов
            failures.append(run_tests([pytest, "-q"] + tests, root, {1}, deadline))
    return "\n\n".join(f for f in failures if f)


def first_failure(edited: List[str], deadline: Optional[float] = None) -> str:
    if deadline is None:
        deadline = time.time() + STOP_BUDGET
    existing = [p for p in edited if os.path.isfile(p)]
    ts_files = [p for p in existing if p.endswith((".ts", ".tsx"))]
    py_files = [p for p in existing if p.endswith((".py", ".pyi"))]
    if enabled("TSC") and ts_files:
        errors = type_errors(ts_files, deadline)
        if errors:
            return "tsc нашел ошибки типов в правленых файлах, почини их.\n" + "\n".join(errors[:MAX_ERRORS])
    if enabled("TYPES") and py_files:
        errors = python_type_errors(py_files, deadline)
        if errors:
            return "pyright или mypy нашел ошибки типов в правленых файлах, почини их.\n" + "\n".join(errors[:MAX_ERRORS])
    if opted_in("TESTS"):
        failures = related_test_failures(existing, deadline)
        if failures:
            return "Тесты по правленым файлам падают. Почини код или напиши, что тест красный нарочно.\n" + failures
    return ""


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
    if not data.get("stop_hook_active"):
        reason = first_failure(edited)
        if reason:
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
