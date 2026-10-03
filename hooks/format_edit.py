#!/usr/bin/env python3
"""PostToolUse для Edit, Write, MultiEdit. Prettier и eslint --fix по одному файлу, учет правленых .ts."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import enabled, find_bin, find_up, node_env, read_input, run, session_state  # noqa: E402

PRETTIER_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".css", ".scss", ".md"}
ESLINT_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
TS_EXT = {".ts", ".tsx"}
SKIP_DIRS = {"node_modules", "dist", "build", ".next", "coverage", "__generated__"}
ESLINT_CONFIGS = [
    "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts",
    ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml", ".eslintrc",
]
MAX_LINES = 20


def skipped(path: str) -> bool:
    return bool(set(path.split(os.sep)) & SKIP_DIRS) or ".generated." in os.path.basename(path)


def remember(session_id: str, path: str) -> None:
    with session_state(session_id) as state:
        edited = state.setdefault("edited", [])
        if path not in edited:
            edited.append(path)


def run_prettier(path: str, env: dict) -> None:
    prettier = find_bin(os.path.dirname(path), "prettier")
    if not prettier:
        return
    try:
        subprocess.run([prettier, "--write", path], capture_output=True, timeout=15, env=env,
                       cwd=os.path.dirname(path))
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_eslint(path: str, env: dict) -> str:
    eslint = find_bin(os.path.dirname(path), "eslint")
    config = find_up(os.path.dirname(path), ESLINT_CONFIGS)
    if not eslint or not config:
        return ""
    try:
        proc = subprocess.run([eslint, "--fix", "--quiet", "--no-color", path], capture_output=True, text=True,
                              timeout=30, env=env, cwd=os.path.dirname(config))
    except (OSError, subprocess.TimeoutExpired):
        return ""
    # Код 1 это оставшиеся ошибки, код 2 это поломка конфига, ее не вешаем на Claude
    if proc.returncode != 1:
        return ""
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return "\n".join(lines[:MAX_LINES])


def main() -> int:
    data = read_input()
    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not path or not os.path.isfile(path):
        return 0
    path = os.path.realpath(path)
    if skipped(path):
        return 0
    ext = os.path.splitext(path)[1]
    if ext in TS_EXT:
        remember(data.get("session_id", ""), path)
    if not enabled("FORMAT"):
        return 0
    env = node_env()
    if ext in PRETTIER_EXT:
        run_prettier(path, env)
    if ext in ESLINT_EXT:
        errors = run_eslint(path, env)
        if errors:
            sys.stderr.write("eslint нашел ошибки в %s, почини их.\n%s\n" % (path, errors))
            return 2
    return 0


if __name__ == "__main__":
    run(main)
