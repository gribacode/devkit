#!/usr/bin/env python3
"""PreToolUse для Read, Edit, Write, MultiEdit, Grep. Не дает трогать файлы с секретами."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import enabled, is_secret_path, read_input, run  # noqa: E402


def main() -> int:
    if not enabled("GUARD"):
        return 0
    tool_input = read_input().get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if is_secret_path(path):
        sys.stderr.write(
            "devkit закрыл доступ к %s, это файл с секретами. Если он правда нужен, открой его сам.\n" % path
        )
        return 2
    return 0


if __name__ == "__main__":
    run(main)
