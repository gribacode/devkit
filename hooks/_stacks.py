"""Выбор инструментов по файлу для format_edit и stop. Только чистые функции и stdlib."""
import os
import re
import shutil
from typing import List, Optional, Tuple

from _common import find_bin, find_up

JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
PY_EXT = {".py", ".pyi"}
NGINX_DIRS = {"nginx", "conf.d", "sites-available", "sites-enabled"}
COMPOSE_RE = re.compile(r"^(compose(\.[\w-]+)?|docker-compose[\w.-]*)\.ya?ml$")
COMPOSE_BASE = ["compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"]
BIOME_CONFIGS = ["biome.json", "biome.jsonc"]
PY_ROOT_MARKERS = ["pyproject.toml", "pyrightconfig.json", "mypy.ini", ".mypy.ini", "setup.cfg"]


def kind(path: str) -> Optional[str]:
    name = os.path.basename(path)
    if name in ("Dockerfile", "Containerfile") or name.startswith("Dockerfile.") or name.endswith(".Dockerfile"):
        return "dockerfile"
    if COMPOSE_RE.match(name):
        return "compose"
    ext = os.path.splitext(name)[1]
    if ext in JS_EXT:
        return "js"
    if ext in PY_EXT:
        return "python"
    if ext == ".conf" and (name.startswith("nginx") or set(os.path.dirname(path).split(os.sep)) & NGINX_DIRS):
        return "nginx"
    return None


def _tool_with_config(path: str, binary: str, configs: List[str]) -> Optional[Tuple[str, str]]:
    folder = os.path.dirname(path)
    config = find_up(folder, configs)
    found = find_bin(folder, binary)
    return (found, os.path.dirname(config)) if config and found else None


def biome(path: str) -> Optional[Tuple[str, str]]:
    return _tool_with_config(path, "biome", BIOME_CONFIGS)


def oxlint(path: str) -> Optional[Tuple[str, str]]:
    return _tool_with_config(path, "oxlint", [".oxlintrc.json"])


def python_bin(path: str, name: str) -> Optional[str]:
    # Сначала окружение проекта, потом глобальный бинарь
    for venv in (".venv", "venv"):
        found = find_up(os.path.dirname(path), [os.path.join(venv, "bin", name)])
        if found and os.access(found, os.X_OK):
            return found
    return shutil.which(name)


def _pyproject_has(path: str, tool: str) -> Optional[str]:
    pyproject = find_up(os.path.dirname(path), ["pyproject.toml"])
    if not pyproject:
        return None
    try:
        with open(pyproject, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    return pyproject if re.search(r"^\[tool\.%s[\].]" % re.escape(tool), text, re.M) else None


def ruff_root(path: str) -> Optional[str]:
    config = find_up(os.path.dirname(path), ["ruff.toml", ".ruff.toml"]) or _pyproject_has(path, "ruff")
    return os.path.dirname(config) if config else None


def python_typechecker(path: str) -> Optional[str]:
    folder = os.path.dirname(path)
    if find_up(folder, ["pyrightconfig.json"]) or _pyproject_has(path, "pyright"):
        return "pyright"
    if find_up(folder, ["mypy.ini", ".mypy.ini"]) or _pyproject_has(path, "mypy"):
        return "mypy"
    return None


def python_root(path: str) -> str:
    marker = find_up(os.path.dirname(path), PY_ROOT_MARKERS)
    return os.path.dirname(marker) if marker else os.path.dirname(path)


def compose_files(path: str) -> List[str]:
    # Override сам по себе неполный, проверяем его поверх базового файла рядом или выше до корня репозитория
    if os.path.basename(path) in COMPOSE_BASE:
        return [path]
    folder = os.path.dirname(path)
    while True:
        for name in COMPOSE_BASE:
            base = os.path.join(folder, name)
            if os.path.isfile(base):
                return [base, path]
        parent = os.path.dirname(folder)
        if os.path.exists(os.path.join(folder, ".git")) or parent == folder:
            return [path]
        folder = parent
