#!/usr/bin/env python3
"""PreToolUse для Bash. Блокирует разрушительные команды, коммиты и пуши, чтение секретов."""
import os
import re
import shlex
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import enabled, is_secret_path, read_input, run  # noqa: E402

HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)(\w+)\1([^\n]*)\n(?:.*?\n)?[ \t]*\2[ \t]*(?=\n|$)", re.DOTALL)
SEPARATOR_CHARS = set("();&|")
WRAPPERS = {"env", "command", "builtin", "nohup", "time", "exec", "nice"}
XARGS_OPTS_WITH_VALUE = {"-I", "-n", "-P", "-L", "-d", "-E", "-s"}
SHELLS = {"sh", "bash", "zsh"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
PIPE_TO_SHELL = re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(sh|bash|zsh)\b")
SQL_CLIENT = re.compile(r"\b(psql|mysql|sqlite3)\b|\bdb\s+execute\b")
SQL_DANGER = re.compile(r"\b(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE)\b", re.IGNORECASE)
RM_DANGER = {"/", "/*", "~", "~/*", "$HOME", "${HOME}", "$HOME/*", "*", ".", "./*", ".."}
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree"}
READERS = {"cat", "less", "more", "head", "tail", "bat", "source", "."}


def _segments(command: str) -> List[List[str]]:
    # Тело heredoc это данные, а не команды. Подстановки $(...) и `...` режем как отдельные команды
    text = HEREDOC.sub(r" \3", command)
    text = text.replace("\\\n", " ").replace("\n", " ; ").replace("$(", " ( ").replace("`", " ; ")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = text.split()
    segments: List[List[str]] = []
    current: List[str] = []
    for token in tokens:
        if token and set(token) <= SEPARATOR_CHARS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _unwrap(t: List[str]) -> List[str]:
    while t:
        head = os.path.basename(t[0])
        if ASSIGNMENT.match(t[0]):
            t = t[1:]
        elif head in WRAPPERS:
            t = t[1:]
            while t and t[0].startswith("-"):
                t = t[1:]
        elif head == "xargs":
            t = t[1:]
            while t and t[0].startswith("-"):
                t = t[2:] if t[0] in XARGS_OPTS_WITH_VALUE else t[1:]
        else:
            break
    return [os.path.basename(t[0]) or t[0]] + t[1:] if t else []


def _check_rm(t: List[str]) -> Optional[str]:
    if not t or t[0] != "rm":
        return None
    short = "".join(a[1:] for a in t[1:] if a.startswith("-") and not a.startswith("--"))
    recursive = "r" in short or "R" in short or "--recursive" in t
    force = "f" in short or "--force" in t
    if not (recursive and force):
        return None
    home = os.path.expanduser("~")
    for arg in t[1:]:
        if arg.startswith("-"):
            continue
        norm = arg.rstrip("/") or "/"
        if arg in RM_DANGER or norm in RM_DANGER or norm == home:
            return "rm -rf по %s снесет слишком много" % arg
    return None


def _check_git(t: List[str]) -> Optional[str]:
    if not t or t[0] != "git":
        return None
    i = 1
    while i < len(t) and t[i].startswith("-"):
        i += 2 if t[i] in GIT_OPTS_WITH_VALUE else 1
    if i >= len(t):
        return None
    sub, rest = t[i], t[i + 1:]
    if sub in ("commit", "push"):
        return "git %s делаешь ты сам" % sub
    if sub == "reset" and "--hard" in rest:
        return "git reset --hard выбросит незакоммиченные правки"
    if sub == "clean" and any(a == "--force" or (a.startswith("-") and not a.startswith("--") and "f" in a) for a in rest):
        return "git clean -f удалит неотслеживаемые файлы"
    if sub in ("checkout", "restore") and "." in rest:
        return "git %s . откатит все правки в рабочем дереве" % sub
    return None


def _check_prisma(t: List[str]) -> Optional[str]:
    if "prisma" not in t:
        return None
    rest = t[t.index("prisma") + 1:]
    if rest[:2] == ["migrate", "reset"]:
        return "prisma migrate reset сотрет базу"
    if rest[:2] == ["db", "push"] and ("--force-reset" in rest or "--accept-data-loss" in rest):
        return "prisma db push с потерей данных"
    return None


def _check_misc(t: List[str]) -> Optional[str]:
    if not t:
        return None
    if t[0] == "sudo":
        return "sudo запускаешь ты сам"
    if t[0] == "chmod" and "-R" in t and "777" in t:
        return "chmod -R 777 открывает все всем"
    if t[0] in READERS and any(is_secret_path(a) for a in t[1:] if not a.startswith("-")):
        return "чтение файла с секретами"
    return None


PUBLISH = {("npm", "publish"), ("pnpm", "publish"), ("yarn", "publish"), ("twine", "upload"), ("uv", "publish"),
           ("poetry", "publish")}


def _check_docker(t: List[str]) -> Optional[str]:
    if not t:
        return None
    if t[0] == "docker-compose":
        rest = t[1:]
    elif t[0] == "docker" and t[1:2] == ["compose"]:
        rest = t[2:]
    else:
        rest = None
    if rest is not None:
        if "down" in rest and {"-v", "--volumes"} & set(rest[rest.index("down") + 1:]):
            return "docker compose down -v удалит тома с данными"
        return None
    if t[0] == "docker" and t[1:3] in (["volume", "rm"], ["volume", "prune"]):
        return "docker volume %s удалит данные в томах" % t[2]
    if t[0] == "docker" and t[1:3] == ["system", "prune"]:
        return "docker system prune удалит образы, тома и кеш"
    return None


def _check_publish(t: List[str]) -> Optional[str]:
    if "--dry-run" in t:
        return None
    if tuple(t[:2]) in PUBLISH or t[:3] == ["yarn", "npm", "publish"]:
        return "публикацию пакета делаешь ты сам"
    return None


def check_command(command: str) -> Optional[str]:
    if not command.strip():
        return None
    if PIPE_TO_SHELL.search(command):
        return "скачивание скрипта сразу в shell"
    if SQL_CLIENT.search(command) and SQL_DANGER.search(command):
        return "DROP или TRUNCATE в базе"
    for segment in _segments(command):
        t = _unwrap(segment)
        if t and t[0] in SHELLS and "-c" in t[1:-1]:
            reason = check_command(t[t.index("-c") + 1])
            if reason:
                return reason
            continue
        for check in (_check_rm, _check_git, _check_prisma, _check_docker, _check_publish, _check_misc):
            reason = check(t)
            if reason:
                return reason
    return None


def main() -> int:
    if not enabled("GUARD"):
        return 0
    command = (read_input().get("tool_input") or {}).get("command") or ""
    reason = check_command(command)
    if reason:
        sys.stderr.write("devkit заблокировал команду, %s. Если она правда нужна, запусти ее сам через !\n" % reason)
        return 2
    return 0


if __name__ == "__main__":
    run(main)
