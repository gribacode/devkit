#!/usr/bin/env python3
"""PostToolUse для Edit, Write, MultiEdit. Форматирует и линтует файл по его стеку, учитывает правленые файлы для Stop."""
import json
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import enabled, find_bin, find_up, node_env, opted_in, read_input, run, session_state  # noqa: E402
from _stacks import COMPOSE_BASE, JS_EXT, biome, compose_files, kind, oxlint, python_bin, ruff_root  # noqa: E402

PRETTIER_EXT = JS_EXT | {".json", ".css", ".scss", ".md"}
BIOME_EXT = JS_EXT | {".json", ".jsonc", ".css"}
TRACKED_EXT = {".ts", ".tsx", ".py", ".pyi"}
SKIP_DIRS = {"node_modules", "dist", "build", ".next", "coverage", "__generated__",
             ".venv", "venv", "__pycache__", ".mypy_cache", ".ruff_cache"}
ESLINT_CONFIGS = [
    "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts",
    ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml", ".eslintrc",
]
MAX_LINES = 20
# prettier, oxlint и eslint идут подряд и вместе должны уложиться в таймаут хука 60 секунд
PRETTIER_TIMEOUT = 15
OXLINT_TIMEOUT = 15
ESLINT_TIMEOUT = 25
COMPOSE_ENV_NOISE = ("env file", "required variable")
# Override без базового файла неполон, отсутствие image или build у сервиса тогда не ошибка
COMPOSE_PARTIAL_NOISE = ("neither an image nor a build context",)
# 125 это ошибка самого docker CLI, например нет плагина compose
COMPOSE_FAIL_CODES = set(range(1, 256)) - {125}


def skipped(path: str) -> bool:
    return bool(set(path.split(os.sep)) & SKIP_DIRS) or ".generated." in os.path.basename(path)


def remember(session_id: str, path: str) -> None:
    with session_state(session_id) as state:
        edited = state.setdefault("edited", [])
        if path not in edited:
            edited.append(path)


def run_tool(cmd: List[str], cwd: str, env: Dict[str, str], timeout: int, fail_codes: Optional[Set[int]]) -> str:
    # fail_codes None значит любой ненулевой код. Остальные коды это поломка инструмента, ее не вешаем на Claude
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    failed = proc.returncode != 0 if fail_codes is None else proc.returncode in fail_codes
    if not failed:
        return ""
    lines = [line for line in (proc.stdout + "\n" + proc.stderr).splitlines() if line.strip()]
    return "\n".join(lines[:MAX_LINES])


def run_prettier(path: str, env: Dict[str, str]) -> None:
    prettier = find_bin(os.path.dirname(path), "prettier")
    if not prettier:
        return
    # prettier читает .prettierignore из cwd, поэтому запускаем из его каталога
    ignore = find_up(os.path.dirname(path), [".prettierignore"])
    cwd = os.path.dirname(ignore) if ignore else os.path.dirname(path)
    try:
        subprocess.run([prettier, "--write", path], capture_output=True, timeout=PRETTIER_TIMEOUT, env=env, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_eslint(path: str, env: Dict[str, str]) -> str:
    eslint = find_bin(os.path.dirname(path), "eslint")
    config = find_up(os.path.dirname(path), ESLINT_CONFIGS)
    if not eslint or not config:
        return ""
    # Код 1 это оставшиеся ошибки, код 2 это поломка конфига
    return run_tool([eslint, "--fix", "--quiet", "--no-color", path], os.path.dirname(config), env, ESLINT_TIMEOUT, {1})


def check_web(path: str, ext: str, env: Dict[str, str]) -> str:
    tool = biome(path)
    if tool:
        if ext not in BIOME_EXT:
            return ""
        errors = run_tool([tool[0], "check", "--write", "--no-errors-on-unmatched", path], tool[1], env, 30, {1})
        return errors if ext in JS_EXT else ""
    if ext in PRETTIER_EXT:
        run_prettier(path, env)
    if ext not in JS_EXT:
        return ""
    found = []
    lint = oxlint(path)
    if lint:
        found.append(run_tool([lint[0], "--fix", path], lint[1], env, OXLINT_TIMEOUT, {1}))
    found.append(run_eslint(path, env))
    return "\n".join(x for x in found if x)


def check_python(path: str, env: Dict[str, str]) -> str:
    root = ruff_root(path)
    ruff = python_bin(path, "ruff") if root else None
    if not root or not ruff:
        return ""
    run_tool([ruff, "format", "--quiet", path], root, env, 15, set())
    # Код 1 это оставшиеся нарушения, код 2 это поломка конфига
    return run_tool([ruff, "check", "--fix", "--quiet", path], root, env, 15, {1})


def check_dockerfile(path: str, env: Dict[str, str]) -> str:
    hadolint = shutil.which("hadolint", path=env.get("PATH"))
    if not hadolint:
        return ""
    return run_tool([hadolint, "--no-color", "--failure-threshold", "error", path], os.path.dirname(path), env, 15, {1})


def check_compose(path: str, env: Dict[str, str]) -> str:
    docker = shutil.which("docker", path=env.get("PATH"))
    if not docker:
        return ""
    files = compose_files(path)
    cmd = [docker, "compose"]
    for name in files:
        cmd += ["-f", name]
    errors = run_tool(cmd + ["config", "-q"], os.path.dirname(path), env, 15, COMPOSE_FAIL_CODES)
    # Нет .env или переменной окружения это не ошибка правки
    noise = COMPOSE_ENV_NOISE
    if len(files) == 1 and os.path.basename(path) not in COMPOSE_BASE:
        noise += COMPOSE_PARTIAL_NOISE
    return "" if any(n in errors for n in noise) else errors


def check_nginx(path: str, env: Dict[str, str]) -> str:
    gixy = shutil.which("gixy", path=env.get("PATH"))
    if not gixy:
        return ""
    try:
        proc = subprocess.run([gixy, "--format", "json", path], capture_output=True, text=True, timeout=15, env=env)
        issues = json.loads(proc.stdout or "[]")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return ""
    high = ["[%s] %s" % (i.get("plugin"), i.get("summary")) for i in issues
            if isinstance(i, dict) and str(i.get("severity", "")).upper() == "HIGH"]
    return "\n".join(high[:MAX_LINES])


CHECKS = {"python": check_python, "dockerfile": check_dockerfile, "compose": check_compose, "nginx": check_nginx}


def main() -> int:
    data = read_input()
    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not path or not os.path.isfile(path):
        return 0
    path = os.path.realpath(path)
    if skipped(path):
        return 0
    ext = os.path.splitext(path)[1]
    stack = kind(path)
    if ext in TRACKED_EXT or (stack == "js" and opted_in("TESTS")):
        remember(data.get("session_id", ""), path)
    if not enabled("FORMAT"):
        return 0
    env = node_env()
    check = CHECKS.get(stack or "")
    errors = check(path, env) if check else check_web(path, ext, env)
    if errors:
        sys.stderr.write("%s нашел ошибки в %s, почини их.\n%s\n" % (stack or "линтер", path, errors))
        return 2
    return 0


if __name__ == "__main__":
    run(main)
