# devkit 0.2: стеки и скиллы aihero. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Расширить devkit автопроверками и правилами для Python, Node.js, Docker, nginx и строгого TS, добавить адаптированные скиллы из mattpocock/skills без дублей с superpowers.

**Architecture:** Хуки остаются теми же процессами. `format_edit.py` и `stop.py` выбирают инструменты через новый модуль чистых функций `hooks/_stacks.py`. Правила по стекам лежат в `refs/stack-*.md`, их читают `/review` и тонкие скиллы `skills/<стек>/SKILL.md`. Новые команды `/grill`, `/handoff`, `/architecture` только с ручным вызовом.

**Tech Stack:** Python 3.9.6 stdlib и `unittest`, формат плагина Claude Code (`commands/`, `skills/`, `hooks/hooks.json`), внешние инструменты проекта: biome, oxlint, eslint, prettier, ruff, pyright, mypy, vitest, jest, pytest, hadolint, docker compose, gixy.

**Spec:** `docs/specs/2026-10-03-devkit-stacks-design.md`

## Global Constraints

- Python 3.9.6: нет `match`, нет `X | Y` и `list[str]` в аннотациях, нет `tomllib`. Типы из `typing`.
- Хуки только stdlib. Хук не роняет сессию: исключение дает exit 0. Блок только exit 2 со stderr после правки или JSON `{"decision":"block"}` на Stop.
- Инструмент запускается, только если у проекта есть его конфиг или локальный бинарь. Нет инструмента, молчаливый exit 0.
- Ни одной новой записи в `hooks.json`. Меняется только таймаут Stop со 120 на 240.
- Выключатели: `DEVKIT_FORMAT=0`, `DEVKIT_TSC=0`, новые `DEVKIT_TYPES=0` и `DEVKIT_TESTS=1` (тесты выключены по умолчанию).
- До 20 строк ошибок линтеров и типов, до 30 строк хвоста вывода тестов. Таймауты: ruff 15 с, biome и oxlint 30 с, hadolint и compose 15 с, gixy 15 с, pyright и mypy 90 с, тесты 90 с.
- Тексты в `commands/`, `refs/`, `skills/` по `refs/style.md`: без тире и ` - ` как паузы, без `ё`, без `;`, двоеточие только в `файл:строка`, без эмодзи. Это проверяет `tests/test_texts.py`.
- Описание каждого `SKILL.md` до 120 символов, одна строка, без двоеточия.
- Адаптированные из aihero файлы начинаются (после фронтматтера) строкой ``Адаптировано из mattpocock/skills (MIT), `<путь>`.`` Источник закреплен на коммите `d81f3a183412e71a5b1e84ca21bc1a35eea03a60`, сырой файл берется по `https://raw.githubusercontent.com/mattpocock/skills/d81f3a183412e71a5b1e84ca21bc1a35eea03a60/<путь>`.
- `git commit` блокирует собственный `guard_bash`. Исполнитель делает `git add` и выдает человеку готовую команду `! git commit -m "..."`. Сам не коммитит и сторож не выключает.
- Полный прогон: `./tests/run.sh`. Отдельный файл: `python3 -m unittest tests.test_stacks -v` из корня репозитория.

## Review Focus

1. compose-override (`docker-compose.override.yml`, `docker-compose.prod.yml`) сам по себе невалиден, у сервиса нет `image`. Хук должен проверять его вместе с базовым файлом рядом, а не блокировать. Тест в Task 3.
2. Нет `.env` или не задана обязательная переменная (`env file ... not found`, `required variable`). Это не ошибка правки, хук не блокирует. Тест в Task 3.
3. Глобальный ruff из Homebrew есть в PATH, а у проекта нет конфига ruff (чужой репозиторий). Ничего не форматируется. Тест в Task 3.
4. mypy при проверке файла заходит в импортируемые модули и ругается на чужие файлы. В причину блока попадают только правленые. Тест в Task 4.
5. `vitest related` без связанных тестов не должен блокировать Stop (`--passWithNoTests`), pytest без собранных тестов (код 5) тоже. Тест в Task 5.

---

### Task 1: `_stacks.py`, выбор инструментов по файлу

**Files:**
- Create: `hooks/_stacks.py`
- Modify: `hooks/_common.py` (добавить `opted_in`)
- Test: `tests/test_stacks.py`, `tests/test_common.py`

**Interfaces:**
- Consumes: `_common.find_up(start, names) -> Optional[str]`, `_common.find_bin(start, name) -> Optional[str]`.
- Produces:
  - `_common.opted_in(name: str) -> bool`, истина только при `DEVKIT_<name>=1`.
  - `_stacks.JS_EXT: Set[str]`, `_stacks.PY_EXT: Set[str]`.
  - `_stacks.kind(path: str) -> Optional[str]`, одно из `"js" "python" "dockerfile" "compose" "nginx"`.
  - `_stacks.biome(path: str) -> Optional[Tuple[str, str]]`, пара (бинарь, каталог конфига).
  - `_stacks.oxlint(path: str) -> Optional[Tuple[str, str]]`, пара (бинарь, каталог конфига).
  - `_stacks.python_bin(path: str, name: str) -> Optional[str]`.
  - `_stacks.ruff_root(path: str) -> Optional[str]`, каталог конфига ruff или `None`.
  - `_stacks.python_typechecker(path: str) -> Optional[str]`, `"pyright"`, `"mypy"` или `None`.
  - `_stacks.python_root(path: str) -> str`.
  - `_stacks.compose_files(path: str) -> List[str]`, файлы для `-f` по порядку.

- [ ] **Step 1: Write the failing test**

`tests/test_stacks.py`:

```python
import os
import sys
import unittest

from tests.helpers import HOOKS, HookTestCase

sys.path.insert(0, HOOKS)
import _stacks  # noqa: E402

KINDS = {
    "src/a.ts": "js", "src/a.tsx": "js", "x.mjs": "js", "x.cjs": "js",
    "app/main.py": "python", "stubs/x.pyi": "python",
    "Dockerfile": "dockerfile", "Dockerfile.dev": "dockerfile", "api.Dockerfile": "dockerfile",
    "Containerfile": "dockerfile",
    "compose.yaml": "compose", "compose.prod.yml": "compose", "docker-compose.yml": "compose",
    "docker-compose.override.yml": "compose",
    "nginx.conf": "nginx", "deploy/nginx/site.conf": "nginx", "etc/conf.d/app.conf": "nginx",
    "sites-enabled/default.conf": "nginx",
    "README.md": None, "data.json": None, "client.conf": None, "values.yaml": None,
}


class KindTest(unittest.TestCase):
    def test_kind_table(self) -> None:
        for rel, expected in KINDS.items():
            self.assertEqual(_stacks.kind(os.path.join("/repo", rel)), expected, rel)


class ToolsTest(HookTestCase):
    def test_biome_needs_config_and_binary(self) -> None:
        path = self.write("p/src/a.ts", "x\n")
        self.assertIsNone(_stacks.biome(path))
        self.write("p/biome.json", "{}")
        self.assertIsNone(_stacks.biome(path))
        binary = self.write("p/node_modules/.bin/biome", "#!/bin/sh\n", executable=True)
        self.assertEqual(_stacks.biome(path), (binary, os.path.join(self.home, "p")))

    def test_oxlint_needs_config_and_binary(self) -> None:
        path = self.write("p/src/a.ts", "x\n")
        self.write("p/node_modules/.bin/oxlint", "#!/bin/sh\n", executable=True)
        self.assertIsNone(_stacks.oxlint(path))
        self.write("p/.oxlintrc.json", "{}")
        self.assertEqual(_stacks.oxlint(path)[1], os.path.join(self.home, "p"))

    def test_python_bin_prefers_venv(self) -> None:
        path = self.write("p/app/a.py", "x\n")
        venv = self.write("p/.venv/bin/ruff", "#!/bin/sh\n", executable=True)
        self.assertEqual(_stacks.python_bin(path, "ruff"), venv)

    def test_ruff_root(self) -> None:
        path = self.write("p/app/a.py", "x\n")
        self.write("p/pyproject.toml", "[project]\nname = 'x'\n")
        self.assertIsNone(_stacks.ruff_root(path))
        self.write("p/pyproject.toml", "[project]\nname = 'x'\n\n[tool.ruff.lint]\nselect = ['E']\n")
        self.assertEqual(_stacks.ruff_root(path), os.path.join(self.home, "p"))
        other = self.write("q/a.py", "x\n")
        self.write("q/ruff.toml", "")
        self.assertEqual(_stacks.ruff_root(other), os.path.join(self.home, "q"))

    def test_python_typechecker(self) -> None:
        path = self.write("p/app/a.py", "x\n")
        self.assertIsNone(_stacks.python_typechecker(path))
        self.write("p/pyproject.toml", "[tool.mypy]\nstrict = true\n")
        self.assertEqual(_stacks.python_typechecker(path), "mypy")
        self.write("p/pyrightconfig.json", "{}")
        self.assertEqual(_stacks.python_typechecker(path), "pyright")

    def test_python_root(self) -> None:
        path = self.write("p/app/a.py", "x\n")
        self.assertEqual(_stacks.python_root(path), os.path.join(self.home, "p", "app"))
        self.write("p/pyproject.toml", "")
        self.assertEqual(_stacks.python_root(path), os.path.join(self.home, "p"))

    def test_compose_files_pairs_override_with_base(self) -> None:
        base = self.write("c/docker-compose.yml", "services: {}\n")
        override = self.write("c/docker-compose.override.yml", "services: {}\n")
        self.assertEqual(_stacks.compose_files(base), [base])
        self.assertEqual(_stacks.compose_files(override), [base, override])
        lone = self.write("d/compose.prod.yaml", "services: {}\n")
        self.assertEqual(_stacks.compose_files(lone), [lone])


if __name__ == "__main__":
    unittest.main()
```

В `tests/test_common.py` в класс с `test_enabled_reads_env_switch` добавить:

```python
    def test_opted_in_needs_explicit_one(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEVKIT_TESTS", None)
            self.assertFalse(_common.opted_in("TESTS"))
            os.environ["DEVKIT_TESTS"] = "1"
            self.assertTrue(_common.opted_in("TESTS"))
            os.environ["DEVKIT_TESTS"] = "0"
            self.assertFalse(_common.opted_in("TESTS"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_stacks tests.test_common -v`
Expected: FAIL с `ModuleNotFoundError: No module named '_stacks'` и `AttributeError: module '_common' has no attribute 'opted_in'`.

- [ ] **Step 3: Write minimal implementation**

В `hooks/_common.py` после `enabled`:

```python
def opted_in(name: str) -> bool:
    return os.environ.get("DEVKIT_" + name) == "1"
```

`hooks/_stacks.py`:

```python
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
    # Override сам по себе неполный, проверяем его поверх базового файла рядом
    if os.path.basename(path) in COMPOSE_BASE:
        return [path]
    folder = os.path.dirname(path)
    for name in COMPOSE_BASE:
        base = os.path.join(folder, name)
        if os.path.isfile(base):
            return [base, path]
    return [path]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_stacks tests.test_common -v`
Expected: PASS, все тесты.

- [ ] **Step 5: Stage and hand off commit**

```bash
git add hooks/_stacks.py hooks/_common.py tests/test_stacks.py tests/test_common.py
```

Человеку: `! git commit -m "feat: add stack detection helpers for hooks"`

---

### Task 2: `format_edit.py`, диспетчер и JS (biome, oxlint)

**Files:**
- Modify: `hooks/format_edit.py` (переписать целиком, код ниже)
- Test: `tests/test_format_edit.py`

**Interfaces:**
- Consumes: из Task 1 `kind`, `biome`, `oxlint`, `python_bin`, `ruff_root`, `compose_files`, `JS_EXT`, `opted_in`.
- Produces: учет правленых в состоянии сессии `state["edited"]`: всегда `.ts .tsx .py .pyi`, при `DEVKIT_TESTS=1` также `.js .jsx .mjs .cjs`. Функция `run_tool(cmd, cwd, env, timeout, fail_codes) -> str` для Task 3.

- [ ] **Step 1: Write the failing tests**

В `tests/test_format_edit.py` добавить константы и методы в `FormatEditTest`:

```python
FAKE_LOGGER = "#!/bin/sh\necho \"$(basename \"$0\") $@\" >> \"%s/calls.log\"\nexit %d\n"


    def logger(self, rel: str, code: int = 0, out: str = "") -> str:
        body = FAKE_LOGGER % (self.home, code)
        if out:
            body = body.replace("exit", "echo \"%s\"\nexit" % out)
        return self.write(rel, body, executable=True)

    def calls(self) -> str:
        path = os.path.join(self.home, "calls.log")
        return open(path).read() if os.path.exists(path) else ""

    def test_biome_replaces_prettier_and_eslint(self) -> None:
        self.write("b/biome.json", "{}")
        self.logger("b/node_modules/.bin/biome")
        self.logger("b/node_modules/.bin/prettier")
        self.logger("b/node_modules/.bin/eslint")
        self.write("b/eslint.config.mjs", "export default []\n")
        path = self.write("b/src/a.ts", "x\n")
        code, _, _ = self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual(code, 0)
        self.assertIn("biome check --write", self.calls())
        self.assertNotIn("prettier", self.calls())
        self.assertNotIn("eslint", self.calls())

    def test_biome_errors_block(self) -> None:
        self.write("b/biome.json", "{}")
        self.logger("b/node_modules/.bin/biome", code=1, out="lint/suspicious/noExplicitAny")
        path = self.write("b/src/a.ts", "x\n")
        code, _, err = self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual(code, 2)
        self.assertIn("noExplicitAny", err)

    def test_oxlint_runs_before_eslint_and_blocks(self) -> None:
        path = self.project(FAKE_ESLINT_OK)
        self.write("proj/.oxlintrc.json", "{}")
        self.logger("proj/node_modules/.bin/oxlint", code=1, out="eslint(no-unused-vars)")
        code, _, err = self.run_hook("format_edit.py", self.payload(path))
        self.assertEqual(code, 2)
        self.assertIn("oxlint --fix", self.calls())
        self.assertIn("no-unused-vars", err)

    def test_js_recorded_only_with_tests_opt_in(self) -> None:
        path = self.write("bare/src/a.js", "x\n")
        self.run_hook("format_edit.py", self.payload(path))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude/devkit/state/s1.json")) and self.edited())
        self.run_hook("format_edit.py", self.payload(path), env={"DEVKIT_TESTS": "1"})
        self.assertEqual(self.edited(), [os.path.realpath(path)])

    def test_python_file_recorded(self) -> None:
        path = self.write("py/app/a.py", "x\n")
        self.run_hook("format_edit.py", self.payload(path), env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(self.edited(), [os.path.realpath(path)])

    def test_skips_venv_and_pycache(self) -> None:
        for rel in ("py/.venv/lib/x.py", "py/app/__pycache__/x.py"):
            path = self.write(rel, "x\n")
            code, out, err = self.run_hook("format_edit.py", self.payload(path))
            self.assertEqual((code, out, err), (0, "", ""), rel)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_format_edit -v`
Expected: FAIL в `test_biome_*`, `test_oxlint_*`, `test_js_recorded_only_with_tests_opt_in`, `test_python_file_recorded`. Старые тесты проходят.

- [ ] **Step 3: Write implementation**

`hooks/format_edit.py` целиком. Обработчики для Python, Docker и nginx здесь заглушками `return ""`, их наполняет Task 3.

```python
#!/usr/bin/env python3
"""PostToolUse для Edit, Write, MultiEdit. Форматирует и линтует файл по его стеку, учитывает правленые файлы для Stop."""
import os
import subprocess
import sys
from typing import Dict, List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import enabled, find_bin, find_up, node_env, opted_in, read_input, run, session_state  # noqa: E402
from _stacks import JS_EXT, biome, kind, oxlint  # noqa: E402

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
        subprocess.run([prettier, "--write", path], capture_output=True, timeout=15, env=env, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_eslint(path: str, env: Dict[str, str]) -> str:
    eslint = find_bin(os.path.dirname(path), "eslint")
    config = find_up(os.path.dirname(path), ESLINT_CONFIGS)
    if not eslint or not config:
        return ""
    # Код 1 это оставшиеся ошибки, код 2 это поломка конфига
    return run_tool([eslint, "--fix", "--quiet", "--no-color", path], os.path.dirname(config), env, 30, {1})


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
        found.append(run_tool([lint[0], "--fix", path], lint[1], env, 30, {1}))
    found.append(run_eslint(path, env))
    return "\n".join(x for x in found if x)


def check_python(path: str, env: Dict[str, str]) -> str:
    return ""


def check_dockerfile(path: str, env: Dict[str, str]) -> str:
    return ""


def check_compose(path: str, env: Dict[str, str]) -> str:
    return ""


def check_nginx(path: str, env: Dict[str, str]) -> str:
    return ""


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
```

Старый тест `test_eslint_errors_go_back_to_claude` проверяет только `no-undef` в stderr и код 2, новый текст сообщения ему подходит.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_format_edit tests.test_manifest -v`
Expected: PASS, включая старые тесты и `BrokenInputTest`.

- [ ] **Step 5: Stage and hand off commit**

```bash
git add hooks/format_edit.py tests/test_format_edit.py
```

Человеку: `! git commit -m "feat: dispatch format hook by stack, add biome and oxlint"`

---

### Task 3: `format_edit.py`, Python, Dockerfile, compose, nginx

**Files:**
- Modify: `hooks/format_edit.py` (заменить 4 заглушки и импорт из `_stacks`)
- Test: `tests/test_format_edit.py`

**Interfaces:**
- Consumes: `run_tool` из Task 2. `python_bin`, `ruff_root`, `compose_files` из Task 1.
- Produces: ничего нового для других задач.

- [ ] **Step 1: Write the failing tests**

Новый класс в `tests/test_format_edit.py`. Фейковые бинари лежат в `<home>/bin`, `PATH` в тестах `<home>/bin:/usr/bin:/bin`, чтобы настоящие ruff и docker из Homebrew не мешали.

```python
FAKE_GIXY_HIGH = """#!/bin/sh
echo '[{"plugin": "host_spoofing", "summary": "Host header forgery", "severity": "HIGH"}, {"plugin": "add_header_redefinition", "summary": "Nested add_header", "severity": "MEDIUM"}]'
exit 1
"""
FAKE_GIXY_LOW = """#!/bin/sh
echo '[{"plugin": "add_header_redefinition", "summary": "Nested add_header", "severity": "MEDIUM"}]'
exit 1
"""


class StackChecksTest(HookTestCase):
    def payload(self, path: str) -> dict:
        return {"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "Edit",
                "tool_input": {"file_path": path}}

    def fake(self, name: str, code: int = 0, out: str = "", err: str = "") -> None:
        body = "#!/bin/sh\necho \"%s $@\" >> \"%s/calls.log\"\n" % (name, self.home)
        if out:
            body += "echo '%s'\n" % out
        if err:
            body += "echo '%s' >&2\n" % err
        self.write("bin/" + name, body + "exit %d\n" % code, executable=True)

    def hook(self, path: str):
        env = {"PATH": "%s/bin:/usr/bin:/bin" % self.home}
        return self.run_hook("format_edit.py", self.payload(path), env=env)

    def calls(self) -> str:
        path = os.path.join(self.home, "calls.log")
        return open(path).read() if os.path.exists(path) else ""

    def test_ruff_without_config_does_nothing(self) -> None:
        self.fake("ruff", code=1, out="E501")
        path = self.write("py/app/a.py", "x\n")
        self.assertEqual(self.hook(path)[0], 0)
        self.assertEqual(self.calls(), "")

    def test_ruff_formats_and_blocks_on_remaining_errors(self) -> None:
        self.write("py/pyproject.toml", "[tool.ruff]\nline-length = 100\n")
        self.fake("ruff", code=1, out="app/a.py:1:1: F401 unused import")
        path = self.write("py/app/a.py", "x\n")
        code, _, err = self.hook(path)
        self.assertEqual(code, 2)
        self.assertIn("ruff format", self.calls())
        self.assertIn("ruff check --fix", self.calls())
        self.assertIn("F401", err)

    def test_ruff_from_venv_wins(self) -> None:
        self.write("py/ruff.toml", "")
        self.fake("ruff", code=1, out="GLOBAL")
        self.write("py/.venv/bin/ruff", "#!/bin/sh\nexit 0\n", executable=True)
        path = self.write("py/app/a.py", "x\n")
        self.assertEqual(self.hook(path)[0], 0)

    def test_hadolint_blocks_on_error(self) -> None:
        self.fake("hadolint", code=1, out="DL3006 error: Always tag the version of an image explicitly")
        path = self.write("d/Dockerfile", "FROM node\n")
        code, _, err = self.hook(path)
        self.assertEqual(code, 2)
        self.assertIn("--failure-threshold error", self.calls())
        self.assertIn("DL3006", err)

    def test_dockerfile_without_hadolint_is_silent(self) -> None:
        path = self.write("d/Dockerfile", "FROM node\n")
        self.assertEqual(self.hook(path), (0, "", ""))

    def test_compose_error_blocks(self) -> None:
        self.fake("docker", code=15, err="yaml: line 3: mapping values are not allowed in this context")
        path = self.write("c/compose.yaml", "services:\n  a: b: c\n")
        code, _, err = self.hook(path)
        self.assertEqual(code, 2)
        self.assertIn("mapping values", err)

    def test_compose_override_checked_with_base(self) -> None:
        self.fake("docker")
        base = self.write("c/docker-compose.yml", "services: {}\n")
        override = self.write("c/docker-compose.override.yml", "services: {}\n")
        self.assertEqual(self.hook(override)[0], 0)
        self.assertIn("compose -f %s -f %s config -q" % (base, override), self.calls())

    def test_compose_missing_env_does_not_block(self) -> None:
        for message in ("env file /x/.env not found: stat /x/.env: no such file or directory",
                        'required variable DB_PASSWORD is missing a value: set it'):
            self.fake("docker", code=1, err=message)
            path = self.write("c/compose.yaml", "services: {}\n")
            self.assertEqual(self.hook(path)[0], 0, message)

    def test_gixy_blocks_only_on_high(self) -> None:
        self.write("bin/gixy", FAKE_GIXY_HIGH, executable=True)
        path = self.write("n/nginx.conf", "events {}\n")
        code, _, err = self.hook(path)
        self.assertEqual(code, 2)
        self.assertIn("host_spoofing", err)
        self.assertNotIn("add_header_redefinition", err)
        self.write("bin/gixy", FAKE_GIXY_LOW, executable=True)
        self.assertEqual(self.hook(path)[0], 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_format_edit.StackChecksTest -v`
Expected: FAIL во всех блокирующих тестах, потому что заглушки возвращают пустую строку. `test_ruff_without_config_does_nothing` и `test_dockerfile_without_hadolint_is_silent` уже проходят.

- [ ] **Step 3: Write implementation**

В `hooks/format_edit.py` импорт:

```python
import json
import shutil

from _stacks import JS_EXT, biome, compose_files, kind, oxlint, python_bin, ruff_root  # noqa: E402
```

Константа рядом с остальными:

```python
COMPOSE_ENV_NOISE = ("env file", "required variable")
```

Заменить четыре заглушки:

```python
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
    cmd = [docker, "compose"]
    for name in compose_files(path):
        cmd += ["-f", name]
    errors = run_tool(cmd + ["config", "-q"], os.path.dirname(path), env, 15, None)
    # Нет .env или переменной окружения это не ошибка правки
    return "" if any(noise in errors for noise in COMPOSE_ENV_NOISE) else errors


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_format_edit -v`
Expected: PASS, все тесты файла.

- [ ] **Step 5: Ручная проверка формата gixy**

Run: `pipx run gixy-ng --help 2>&1 | grep -i -A2 format || echo "нет pipx или сети"`
Expected: в справке есть `--format` с вариантом `json`. Если вывода нет из-за сети, отметить это в отчете задачи, а не придумывать.

- [ ] **Step 6: Stage and hand off commit**

```bash
git add hooks/format_edit.py tests/test_format_edit.py
```

Человеку: `! git commit -m "feat: lint python, dockerfile, compose and nginx after edit"`

---

### Task 4: `stop.py`, проверка типов Python

**Files:**
- Modify: `hooks/stop.py`
- Test: `tests/test_stop.py`

**Interfaces:**
- Consumes: `python_typechecker`, `python_root`, `python_bin` из Task 1. `type_errors` (tsc) уже есть.
- Produces: `stop.python_type_errors(files: List[str]) -> List[str]`, `stop.first_failure(edited: List[str]) -> str` (пустая строка значит чисто). Task 5 добавляет в `first_failure` третью ступень.

- [ ] **Step 1: Write the failing tests**

В `tests/test_stop.py`:

```python
FAKE_PYRIGHT = """#!/bin/sh
echo "$PWD/app/a.py"
echo "  $PWD/app/a.py:3:5 - error: Type \\"str\\" is not assignable to \\"int\\""
echo "  $PWD/app/old.py:1:1 - error: legacy"
echo "2 errors"
exit 1
"""
FAKE_MYPY = """#!/bin/sh
echo "app/a.py:3: error: Incompatible types in assignment  [assignment]"
echo "app/dep.py:9: error: imported module problem  [misc]"
exit 1
"""
```

Методы в `StopTest`:

```python
    def py_project(self, checker: str, script: str) -> str:
        section = "[tool.pyright]\n" if checker == "pyright" else "[tool.mypy]\n"
        self.write("py/pyproject.toml", section)
        self.write("py/.venv/bin/" + checker, script, executable=True)
        self.write("py/app/old.py", "x\n")
        return os.path.realpath(self.write("py/app/a.py", "x: int = 'a'\n"))

    def test_pyright_blocks_on_edited_file_only(self) -> None:
        path = self.py_project("pyright", FAKE_PYRIGHT)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload())
        result = json.loads(out)
        self.assertEqual(result["decision"], "block")
        self.assertIn("a.py:3:5", result["reason"])
        self.assertNotIn("old.py", result["reason"])

    def test_mypy_filters_imported_modules(self) -> None:
        path = self.py_project("mypy", FAKE_MYPY)
        self.set_state(edited=[path], prompt_at=time.time())
        _, out, _ = self.run_hook("stop.py", self.payload())
        reason = json.loads(out)["reason"]
        self.assertIn("app/a.py:3", reason)
        self.assertNotIn("dep.py", reason)

    def test_types_switch_off(self) -> None:
        path = self.py_project("pyright", FAKE_PYRIGHT)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload(), env={"DEVKIT_TYPES": "0"})
        self.assertEqual((code, out), (0, ""))

    def test_python_without_typechecker_config_is_silent(self) -> None:
        self.write("py/.venv/bin/pyright", FAKE_PYRIGHT, executable=True)
        path = os.path.realpath(self.write("py/app/a.py", "x\n"))
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload())
        self.assertEqual((code, out), (0, ""))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_stop -v`
Expected: FAIL в `test_pyright_blocks_on_edited_file_only` и `test_mypy_filters_imported_modules` (`json.decoder.JSONDecodeError`, вывод пуст).

- [ ] **Step 3: Write implementation**

В `hooks/stop.py` импорты:

```python
from typing import Dict, List, Tuple

from _stacks import python_bin, python_root, python_typechecker  # noqa: E402
```

Константы:

```python
PY_ERROR_RES = (
    re.compile(r"^\s*(?P<file>.+?\.pyi?):\d+:\d+ - error:"),  # pyright
    re.compile(r"^(?P<file>.+?\.pyi?):\d+(?::\d+)?: error:"),  # mypy
)
```

Новая функция после `type_errors`:

```python
def python_type_errors(files: List[str]) -> List[str]:
    edited = {os.path.realpath(p) for p in files}
    groups: Dict[Tuple[str, str], List[str]] = {}
    for path in files:
        checker = python_typechecker(path)
        if checker:
            groups.setdefault((python_root(path), checker), []).append(path)
    env = node_env()
    errors: List[str] = []
    for (root, checker), group in groups.items():
        binary = python_bin(group[0], checker)
        if not binary:
            continue
        try:
            proc = subprocess.run([binary] + group, capture_output=True, text=True, timeout=TSC_TIMEOUT, env=env,
                                  cwd=root)
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in proc.stdout.splitlines():
            for regex in PY_ERROR_RES:
                match = regex.match(line)
                if not match:
                    continue
                # mypy заходит в импортируемые модули, оставляем только правленые файлы
                if os.path.realpath(os.path.join(root, match.group("file"))) in edited and line.strip() not in errors:
                    errors.append(line.strip())
                break
    return errors


def first_failure(edited: List[str]) -> str:
    existing = [p for p in edited if os.path.isfile(p)]
    ts_files = [p for p in existing if p.endswith((".ts", ".tsx"))]
    py_files = [p for p in existing if p.endswith((".py", ".pyi"))]
    if enabled("TSC") and ts_files:
        errors = type_errors(ts_files)
        if errors:
            return "tsc нашел ошибки типов в правленых файлах, почини их.\n" + "\n".join(errors[:MAX_ERRORS])
    if enabled("TYPES") and py_files:
        errors = python_type_errors(py_files)
        if errors:
            return "pyright или mypy нашел ошибки типов в правленых файлах, почини их.\n" + "\n".join(errors[:MAX_ERRORS])
    return ""
```

`main` заменить на:

```python
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
```

Докстринг файла: `"""Stop. Проверяет типы правленых .ts и .py, по флагу гоняет связанные тесты, при чистом результате шлет уведомление."""`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_stop -v`
Expected: PASS, включая старые тесты tsc.

- [ ] **Step 5: Stage and hand off commit**

```bash
git add hooks/stop.py tests/test_stop.py
```

Человеку: `! git commit -m "feat: check python types on stop with pyright or mypy"`

---

### Task 5: `stop.py`, тесты по правленым файлам и таймаут хука

**Files:**
- Modify: `hooks/stop.py`, `hooks/hooks.json` (таймаут `stop.py` 120 на 240)
- Test: `tests/test_stop.py`, `tests/test_manifest.py`

**Interfaces:**
- Consumes: `first_failure` из Task 4, `opted_in` из Task 1, `python_bin`, `python_root`.
- Produces: `stop.related_test_failures(files: List[str]) -> str`, `stop.python_tests(root: str, files: List[str]) -> List[str]`.

- [ ] **Step 1: Write the failing tests**

В `tests/test_stop.py`:

```python
FAKE_TEST_RUNNER = "#!/bin/sh\necho \"$(basename \"$0\") $@\" >> \"%s/tests.log\"\necho 'FAIL  src/a.test.ts > sums'\nexit %d\n"
```

Методы в `StopTest`:

```python
    def runner(self, rel: str, code: int) -> None:
        self.write(rel, FAKE_TEST_RUNNER % (self.home, code), executable=True)

    def tests_log(self) -> str:
        path = os.path.join(self.home, "tests.log")
        return open(path).read() if os.path.exists(path) else ""

    def js_project(self) -> str:
        self.write("web/package.json", "{}")
        return os.path.realpath(self.write("web/src/a.js", "x\n"))

    def test_tests_do_not_run_without_opt_in(self) -> None:
        path = self.js_project()
        self.runner("web/node_modules/.bin/vitest", 1)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload())
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(self.tests_log(), "")

    def test_vitest_related_failure_blocks(self) -> None:
        path = self.js_project()
        self.runner("web/node_modules/.bin/vitest", 1)
        self.set_state(edited=[path], prompt_at=time.time())
        _, out, _ = self.run_hook("stop.py", self.payload(), env={"DEVKIT_TESTS": "1"})
        result = json.loads(out)
        self.assertIn("FAIL", result["reason"])
        self.assertIn("vitest related --run --passWithNoTests %s" % path, self.tests_log())

    def test_jest_used_without_vitest(self) -> None:
        path = self.js_project()
        self.runner("web/node_modules/.bin/jest", 0)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload(), env={"DEVKIT_TESTS": "1"})
        self.assertEqual((code, out), (0, ""))
        self.assertIn("jest --findRelatedTests %s --passWithNoTests" % path, self.tests_log())

    def test_pytest_runs_matching_test_file_and_ignores_no_tests(self) -> None:
        self.write("py/pyproject.toml", "")
        path = os.path.realpath(self.write("py/app/calc.py", "x\n"))
        test = os.path.realpath(self.write("py/tests/test_calc.py", "x\n"))
        self.write("py/.venv/lib/test_calc.py", "x\n")
        self.runner("py/.venv/bin/pytest", 5)
        self.set_state(edited=[path], prompt_at=time.time())
        code, out, _ = self.run_hook("stop.py", self.payload(), env={"DEVKIT_TESTS": "1"})
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(self.tests_log().strip(), "pytest -q %s" % test)

    def test_python_tests_finds_edited_tests_directly(self) -> None:
        root = os.path.join(self.home, "py")
        edited = os.path.realpath(self.write("py/tests/test_x.py", "x\n"))
        self.assertEqual(stop.python_tests(root, [edited]), [edited])
```

В `tests/test_manifest.py` в `ManifestTest`:

```python
    def test_stop_timeout_fits_three_checks(self) -> None:
        with open(os.path.join(HOOKS, "hooks.json")) as f:
            stop_hooks = json.load(f)["hooks"]["Stop"][0]["hooks"]
        timeouts = [h["timeout"] for h in stop_hooks if h["command"].endswith('stop.py"')]
        self.assertEqual(timeouts, [240])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_stop tests.test_manifest -v`
Expected: FAIL в `test_vitest_related_failure_blocks`, `test_jest_used_without_vitest`, `test_pytest_runs_matching_test_file_and_ignores_no_tests`, `test_python_tests_finds_edited_tests_directly` (`AttributeError`), `test_stop_timeout_fits_three_checks`.

- [ ] **Step 3: Write implementation**

В `hooks/stop.py` импорт `opted_in` из `_common` и константы:

```python
TEST_TIMEOUT = 90
MAX_TEST_LINES = 30
JS_TEST_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
WALK_SKIP = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
PY_ROOT_MARKERS = ["pyproject.toml", "pyrightconfig.json", "mypy.ini", ".mypy.ini", "setup.cfg"]
```

Функции перед `first_failure`:

```python
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


def run_tests(cmd: List[str], cwd: str, ok_codes: Tuple[int, ...]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TEST_TIMEOUT, env=node_env(), cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode in ok_codes:
        return ""
    lines = [line for line in (proc.stdout + "\n" + proc.stderr).splitlines() if line.strip()]
    return "\n".join(lines[-MAX_TEST_LINES:])


def related_test_failures(files: List[str]) -> str:
    failures: List[str] = []
    for root, group in group_by_root([p for p in files if p.endswith(JS_TEST_EXT)], ["package.json"]).items():
        vitest, jest = find_bin(root, "vitest"), find_bin(root, "jest")
        if vitest:
            failures.append(run_tests([vitest, "related", "--run", "--passWithNoTests"] + group, root, (0,)))
        elif jest:
            failures.append(run_tests([jest, "--findRelatedTests"] + group + ["--passWithNoTests"], root, (0,)))
    for root, group in group_by_root([p for p in files if p.endswith(".py")], PY_ROOT_MARKERS).items():
        pytest, tests = python_bin(group[0], "pytest"), python_tests(root, group)
        if pytest and tests:
            # Код 5 у pytest значит тесты не собраны, это не падение
            failures.append(run_tests([pytest, "-q"] + tests, root, (0, 5)))
    return "\n\n".join(f for f in failures if f)
```

В конец `first_failure` перед `return ""`:

```python
    if opted_in("TESTS"):
        failures = related_test_failures(existing)
        if failures:
            return "Тесты по правленым файлам падают. Почини код или напиши, что тест красный нарочно.\n" + failures
```

В `hooks/hooks.json` у `stop.py` заменить `"timeout": 120` на `"timeout": 240`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./tests/run.sh`
Expected: PASS, весь набор.

- [ ] **Step 5: Stage and hand off commit**

```bash
git add hooks/stop.py hooks/hooks.json tests/test_stop.py tests/test_manifest.py
```

Человеку: `! git commit -m "feat: run related tests on stop behind DEVKIT_TESTS"`

---

### Task 6: `guard_bash.py`, тома docker и публикация пакетов

**Files:**
- Modify: `hooks/guard_bash.py`
- Test: `tests/test_guard_bash.py`

**Interfaces:**
- Consumes: `check_command`, `_unwrap` уже есть.
- Produces: `_check_docker(t: List[str]) -> Optional[str]`, `_check_publish(t: List[str]) -> Optional[str]`, добавлены в цикл `check_command`.

- [ ] **Step 1: Write the failing tests**

В `tests/test_guard_bash.py` в конец списка `BLOCKED`:

```python
    "docker compose down -v",
    "docker compose -f compose.prod.yml down --volumes",
    "docker-compose down -v --remove-orphans",
    "docker volume rm calendar_pgdata",
    "docker volume prune -f",
    "docker system prune -a",
    "npm publish",
    "pnpm publish --access public",
    "yarn npm publish",
    "twine upload dist/*",
    "uv publish",
    "poetry publish --build",
```

В конец списка `ALLOWED` перед `""`:

```python
    "docker compose down",
    "docker compose up -d",
    "docker compose -f compose.yml config -q",
    "docker volume ls",
    "npm pack",
    "npm publish --dry-run",
    'echo "docker volume prune"',
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_guard_bash -v`
Expected: FAIL в `test_blocked` на `docker compose down -v`.

- [ ] **Step 3: Write implementation**

В `hooks/guard_bash.py` константа и две функции перед `check_command`:

```python
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
```

В `check_command` кортеж проверок:

```python
        for check in (_check_rm, _check_git, _check_prisma, _check_docker, _check_publish, _check_misc):
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_guard_bash -v`
Expected: PASS.

- [ ] **Step 5: Stage and hand off commit**

```bash
git add hooks/guard_bash.py tests/test_guard_bash.py
```

Человеку: `! git commit -m "feat: guard docker volume removal and package publishing"`

---

### Task 7: refs по стекам и проверки текстов

**Files:**
- Create: `refs/stack-typescript.md`, `refs/stack-node.md`, `refs/stack-python.md`, `refs/stack-docker.md`, `refs/stack-nginx.md`
- Modify: `tests/test_texts.py`

**Interfaces:**
- Produces: пути `${CLAUDE_PLUGIN_ROOT}/refs/stack-<стек>.md` для Task 8 и Task 12. Функция `texts()` в `test_texts.py` теперь включает `skills/**/*.md`.

- [ ] **Step 1: Write the failing test**

В `tests/test_texts.py` заменить `texts` и `test_refs_exist`:

```python
def texts() -> list:
    found = glob.glob(os.path.join(ROOT, "refs", "*.md")) + glob.glob(os.path.join(ROOT, "commands", "*.md"))
    return sorted(found + glob.glob(os.path.join(ROOT, "skills", "**", "*.md"), recursive=True))
```

```python
    def test_refs_exist(self) -> None:
        names = {"style.md", "review-principles.md", "review-react.md", "review-nest.md", "review-shared.md",
                 "pr-structure.md", "stack-typescript.md", "stack-node.md", "stack-python.md", "stack-docker.md",
                 "stack-nginx.md"}
        self.assertTrue(names <= {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "refs", "*.md"))})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_texts -v`
Expected: FAIL в `test_refs_exist`.

- [ ] **Step 3: Write the refs**

`refs/stack-typescript.md`:

```markdown
# Правила TypeScript

Граница. React в `review-react.md`, Nest в `review-nest.md`, рантайм Node в `stack-node.md`. Здесь только система типов.

1. `any` нет. На границах (ответ API, `JSON.parse`, `catch`) тип `unknown` и сужение через схему (zod, valibot) или type guard.
2. `as` только с комментарием, почему компилятор не выводит тип сам. `as unknown as X` это ошибка дизайна.
3. Non-null `!` только там, где инвариант виден в соседних строках. Иначе явная проверка и ранний выход.
4. `@ts-ignore` нет. `@ts-expect-error` с причиной в той же строке.
5. Литерал, который должен соответствовать типу и сохранить узкий вывод, проверяется через `satisfies`, а не аннотацией.
6. Состояние с вариантами это discriminated union с полем `kind` или `status`, а не набор необязательных полей.
7. `switch` по union исчерпывающий. В `default` присваивание в `never`, чтобы новый вариант ломал сборку.
8. Экспортируемые функции с явным типом возврата. Внутренние полагаются на вывод.
9. `enum` не заводим. Union строковых литералов или объект `as const`.
10. Типы выводятся из источника. `z.infer`, `typeof`, `ReturnType`, сгенерированные типы GraphQL и Prisma. Ручной дубль типа рядом со схемой не пишем.
11. Индексный доступ к массиву и `Record` дает `T | undefined`. Нет `noUncheckedIndexedAccess` в проекте, проверку пишем сами.
12. tsconfig проекта. `strict`, `noUncheckedIndexedAccess`, `noImplicitOverride`, по возможности `exactOptionalPropertyTypes`. Ослабление флага только с комментарием.
13. В тестах частичные объекты через фабрики или `fromPartial` из `@total-typescript/shoehorn`, а не `as Type`.
```

`refs/stack-node.md`:

```markdown
# Правила Node.js

Граница. Nest в `review-nest.md`, типы в `stack-typescript.md`. Здесь рантайм серверного кода.

1. Нет висящих промисов. Каждый промис либо под `await`, либо `void` с явным `.catch`.
2. На `unhandledRejection` и `uncaughtException` процесс логирует и завершается, а не живет в неизвестном состоянии.
3. У каждого внешнего вызова (HTTP, БД, очередь) есть таймаут. `fetch` с `AbortSignal.timeout(ms)`.
4. Graceful shutdown по `SIGTERM` и `SIGINT`. Перестать принимать запросы, дождаться текущих, закрыть пулы, выйти с кодом.
5. Конфиг читается из env один раз на старте и валидируется схемой. Без обязательного значения процесс не стартует. В коде нет разбросанных `process.env.X`.
6. В обработчиках запросов нет синхронного IO (`readFileSync`, `execSync`) и тяжелых циклов. Тяжелое уходит в worker или очередь.
7. Стримы соединяются через `pipeline` из `node:stream/promises`, а не `.pipe`, чтобы ошибки и закрытие доходили до конца.
8. Встроенные модули импортируются с префиксом `node:`.
9. В пакете один формат модулей по полю `type` в `package.json`. Смешение только через явные `.cjs` и `.mjs`.
10. Ошибки это экземпляры `Error` с `cause`, а не строки. Ответ клиенту без стека и внутренних сообщений.
11. Логи структурированные (pino или аналог), без `console.log` в серверном коде, без секретов и персональных данных.
12. Версия Node закреплена в `.nvmrc` или `engines` и совпадает с образом в Dockerfile.
```

`refs/stack-python.md`:

```markdown
# Правила Python

Граница. Форматирование и линт за ruff, типы за pyright или mypy по конфигу проекта. То, что ловит инструмент, здесь не повторяется.

1. Публичные функции с type hints, включая возврат. `list[str]` и `X | None`, если `requires-python` проекта позволяет.
2. Нет голого `except:` и `except Exception: pass`. Ловим конкретное исключение, остальное пробрасываем. Свое исключение через `raise ... from err`.
3. Файлы, соединения и блокировки открываются через `with` или `async with`.
4. Нет изменяемых значений по умолчанию в аргументах. Вместо `def f(x=[])` значение `None` и создание внутри.
5. В `async` коде нет блокирующих вызовов (`requests`, `time.sleep`, синхронный драйвер БД). Блокирующее уходит в `asyncio.to_thread`.
6. Данные извне (запрос, env, файл, ответ API) валидируются на границе через pydantic или dataclass с проверкой. Внутри ходят типизированные объекты, а не `dict`.
7. Конфиг через `pydantic-settings` или один модуль настроек, читается на старте.
8. Логи через `logging.getLogger(__name__)`, без `print` в серверном и библиотечном коде. Аргументы лениво, `log.info("x %s", y)`.
9. Пути через `pathlib.Path`, а не склейку строк.
10. Нет `import *`, циклических импортов и побочных эффектов при импорте модуля.
11. Тесты на pytest. Фикстуры вместо `setUp`, `parametrize` вместо копий теста, `tmp_path` и `monkeypatch` вместо ручной уборки.
12. Зависимости через uv или poetry с lock-файлом в репозитории. Версия Python в `requires-python` и `.python-version`.
```

`refs/stack-docker.md`:

```markdown
# Правила Docker и compose

1. Multi-stage. Сборка с dev-зависимостями отдельно, финальный образ только с рантаймом и артефактами.
2. Базовый образ с тегом версии (`node:22.11-alpine`, `python:3.12-slim`). `latest` и тег без версии запрещены.
3. Порядок слоев ради кеша. Сначала манифесты и lock-файлы, установка зависимостей, потом исходники.
4. Установка строго по lock-файлу. `npm ci`, `pnpm install --frozen-lockfile`, `uv sync --frozen`.
5. Есть `.dockerignore` с `node_modules`, `.git`, `.env*`, `dist`, `.venv`, `__pycache__`.
6. Финальная стадия работает не от root. `USER node` или созданный пользователь.
7. Секреты не попадают в слои, `ARG` и `ENV`. Для сборки `RUN --mount=type=secret`, в рантайме env окружения.
8. `CMD` в exec-форме (`["node", "dist/main.js"]`), чтобы сигналы доходили до процесса. Один процесс на контейнер.
9. У сервиса есть `HEALTHCHECK` или healthcheck в compose.
10. Кеш пакетного менеджера ОС чистится в том же слое. `apk add --no-cache`, `rm -rf /var/lib/apt/lists/*`.
11. compose. `depends_on` с `condition: service_healthy` для БД и брокеров, а не голый список.
12. compose. Данные БД в именованных томах. Порты БД и брокеров наружу не публикуются, в проде только `127.0.0.1:`.
13. compose. Переменные через `env_file` или `${VAR:?}`, пароли открытым текстом в compose-файле не лежат.
14. compose. В продовом файле `restart: unless-stopped` и ограничения ресурсов.
```

`refs/stack-nginx.md`:

```markdown
# Правила nginx

1. `server_tokens off`.
2. Заголовки безопасности на уровне `server` с `always`. `X-Content-Type-Options nosniff`, `Referrer-Policy`, `frame-ancestors` в CSP или `X-Frame-Options`, `Strict-Transport-Security` на HTTPS.
3. `add_header` внутри `location` отменяет все заголовки уровня выше. Нужен свой заголовок в `location`, повтори общие или вынеси их в `include`.
4. Слэш в конце `proxy_pass` меняет путь. `proxy_pass http://api/;` срезает префикс `location`, `proxy_pass http://api;` передает путь как есть. Выбор осознанный и проверен запросом.
5. Прокси передает `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`. За балансировщиком `set_real_ip_from` и `real_ip_header`.
6. Websocket. `proxy_http_version 1.1`, заголовки `Upgrade` и `Connection` через `map $http_upgrade`.
7. SPA. `try_files $uri $uri/ /index.html`, а API и статика с хешем в этот fallback не попадают.
8. Статика с хешем в имени кешируется на год с `immutable`. `index.html` с `no-cache`.
9. gzip включен для текстовых типов, в `gzip_types` есть JS, CSS, JSON, SVG.
10. `client_max_body_size` задан явно под загрузки сервиса.
11. `proxy_read_timeout` и `proxy_connect_timeout` заданы под реальные ответы бэка.
12. Upstream в переменной требует `resolver`. Имена сервисов compose резолвятся через `resolver 127.0.0.11`.
13. `alias` и `location` с префиксом оба заканчиваются слэшем, иначе возможен выход из каталога.
14. В `location` нет `if`, кроме `return` и `rewrite ... last`.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_texts -v`
Expected: PASS, включая `test_no_yo_and_no_dashes_in_prose` по новым файлам.

- [ ] **Step 5: Stage and hand off commit**

```bash
git add refs/stack-*.md tests/test_texts.py
```

Человеку: `! git commit -m "docs: add stack rules for typescript, node, python, docker, nginx"`

---

### Task 8: скиллы по стекам

**Files:**
- Create: `skills/typescript/SKILL.md`, `skills/node/SKILL.md`, `skills/python/SKILL.md`, `skills/docker/SKILL.md`, `skills/nginx/SKILL.md`
- Modify: `tests/test_texts.py`

**Interfaces:**
- Consumes: `refs/stack-*.md` из Task 7.
- Produces: тест `test_skill_frontmatter`, который проверяет каждый будущий `skills/*/SKILL.md` (Task 9 и 10 тоже под ним).

- [ ] **Step 1: Write the failing test**

В `tests/test_texts.py`:

```python
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
STACK_SKILLS = {"typescript", "node", "python", "docker", "nginx"}
```

```python
    def test_skill_frontmatter(self) -> None:
        skills = glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md"))
        self.assertTrue(STACK_SKILLS <= {os.path.basename(os.path.dirname(p)) for p in skills})
        for path in skills:
            with open(path, encoding="utf-8") as f:
                match = FRONTMATTER_RE.match(f.read())
            self.assertIsNotNone(match, path)
            fields = dict(line.split(": ", 1) for line in match.group(1).splitlines() if ": " in line)
            self.assertEqual(fields.get("name"), os.path.basename(os.path.dirname(path)), path)
            description = fields.get("description", "")
            self.assertTrue(0 < len(description) <= 120, path)
            self.assertNotIn(":", description, path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_texts -v`
Expected: FAIL в `test_skill_frontmatter`.

- [ ] **Step 3: Write the skills**

`skills/typescript/SKILL.md`:

```markdown
---
name: typescript
description: Пишешь или правишь код на TypeScript. Строгие типы, unknown на границах, union, satisfies, tsconfig.
---

Прочитай `${CLAUDE_PLUGIN_ROOT}/refs/stack-typescript.md` и пиши по нему. Правила проекта из AGENTS.md, CLAUDE.md и конфига линтера важнее, при расхождении следуй им.
```

`skills/node/SKILL.md`:

```markdown
---
name: node
description: Пишешь серверный код на Node.js. Промисы, таймауты, shutdown, конфиг из env, стримы, ESM и CJS.
---

Прочитай `${CLAUDE_PLUGIN_ROOT}/refs/stack-node.md` и пиши по нему. Для NestJS дополнительно скилл `nestjs-expert`, если он доступен. Правила проекта из AGENTS.md и CLAUDE.md важнее.
```

`skills/python/SKILL.md`:

```markdown
---
name: python
description: Пишешь или правишь код на Python. Типы, исключения, async, валидация на границах, pytest, uv и poetry.
---

Прочитай `${CLAUDE_PLUGIN_ROOT}/refs/stack-python.md` и пиши по нему. Правила проекта из AGENTS.md, CLAUDE.md и `pyproject.toml` важнее.
```

`skills/docker/SKILL.md`:

```markdown
---
name: docker
description: Пишешь или правишь Dockerfile или compose. Слои, кеш, non-root, секреты, healthcheck, тома и порты.
---

Прочитай `${CLAUDE_PLUGIN_ROOT}/refs/stack-docker.md` и пиши по нему. Правила проекта из AGENTS.md и CLAUDE.md важнее.
```

`skills/nginx/SKILL.md`:

```markdown
---
name: nginx
description: Пишешь или правишь конфиг nginx. proxy_pass, заголовки, кеш статики, SPA fallback, websocket, resolver.
---

Прочитай `${CLAUDE_PLUGIN_ROOT}/refs/stack-nginx.md` и пиши по нему. Правила проекта из AGENTS.md и CLAUDE.md важнее.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_texts -v`
Expected: PASS, включая `test_plugin_root_links_resolve` по новым скиллам.

- [ ] **Step 5: Stage and hand off commit**

```bash
git add skills tests/test_texts.py
```

Человеку: `! git commit -m "feat: add thin stack skills pointing at refs"`

---

### Task 9: `codebase-design` и `writing-for-agents` из aihero

**Files:**
- Create: `refs/codebase-design.md`, `skills/codebase-design/SKILL.md`, `skills/codebase-design/DEEPENING.md`, `skills/codebase-design/DESIGN-IT-TWICE.md`, `skills/writing-for-agents/SKILL.md`, `skills/writing-for-agents/SKILL-MECHANICS.md`
- Modify: `commands/agent-lint.md`, `tests/test_texts.py`

**Interfaces:**
- Produces: `${CLAUDE_PLUGIN_ROOT}/refs/codebase-design.md` для Task 11 и Task 12. `${CLAUDE_PLUGIN_ROOT}/skills/writing-for-agents/SKILL.md` для `/agent-lint`.

Правила перевода для всех адаптаций в этой и следующих задачах:

1. Русский по `refs/style.md`. Структура и заголовки оригинала сохраняются, примеры кода не переводятся.
2. Словарь. module модуль, interface интерфейс, implementation реализация, depth глубина, deep глубокий, shallow мелкий, seam шов, adapter адаптер, leverage рычаг, locality локальность, port порт, deletion test тест удаления.
3. «Call the Skill tool with "codebase-design"» заменяется на «прочитай `${CLAUDE_PLUGIN_ROOT}/refs/codebase-design.md`». «with "grilling"» на «веди допрос по `${CLAUDE_PLUGIN_ROOT}/refs/grilling.md`». Упоминания `domain-modeling`, issue-трекера и `setup-matt-pocock-skills` убираются.
4. Эмодзи убираются. Курсив оригинала можно оставить.
5. После фронтматтера (или первой строкой, если его нет) строка атрибуции.

- [ ] **Step 1: Write the failing test**

В `tests/test_texts.py`:

```python
ADAPTED = {
    "refs/codebase-design.md": "skills/engineering/codebase-design/SKILL.md",
    "skills/codebase-design/DEEPENING.md": "skills/engineering/codebase-design/DEEPENING.md",
    "skills/codebase-design/DESIGN-IT-TWICE.md": "skills/engineering/codebase-design/DESIGN-IT-TWICE.md",
    "skills/writing-for-agents/SKILL.md": "skills/productivity/writing-for-agents/SKILL.md",
    "skills/writing-for-agents/SKILL-MECHANICS.md": "skills/productivity/writing-for-agents/SKILL-MECHANICS.md",
}
```

```python
    def test_adapted_files_credit_source(self) -> None:
        for rel, source in ADAPTED.items():
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                self.assertIn("Адаптировано из mattpocock/skills (MIT), `%s`." % source, f.read(), rel)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_texts -v`
Expected: FAIL с `FileNotFoundError` на `refs/codebase-design.md`.

- [ ] **Step 3: Скачать исходники**

```bash
mkdir -p /tmp/aihero && cd /tmp/aihero
BASE=https://raw.githubusercontent.com/mattpocock/skills/d81f3a183412e71a5b1e84ca21bc1a35eea03a60
for p in engineering/codebase-design/SKILL.md engineering/codebase-design/DEEPENING.md \
         engineering/codebase-design/DESIGN-IT-TWICE.md productivity/writing-for-agents/SKILL.md \
         productivity/writing-for-agents/SKILL-MECHANICS.md engineering/improve-codebase-architecture/HTML-REPORT.md; do
  mkdir -p "$(dirname "$p")" && curl -fsSL "$BASE/skills/$p" -o "$p"
done
ls -R
```

Expected: 6 файлов на месте.

- [ ] **Step 4: Написать `refs/codebase-design.md`**

Перевод `engineering/codebase-design/SKILL.md` без фронтматтера. Начало файла:

```markdown
# Дизайн кода

Адаптировано из mattpocock/skills (MIT), `skills/engineering/codebase-design/SKILL.md`.

Проектируй глубокие модули. Много поведения за маленьким интерфейсом, на чистом шве, тестируемо через этот интерфейс. Цель в рычаге для вызывающих, локальности для тех, кто сопровождает, и тестируемости для всех.

## Словарь

Используй эти термины ровно так. Не подменяй их словами «компонент», «сервис», «API», «граница».
```

Дальше разделы оригинала по порядку: определения 7 терминов, «Глубокий и мелкий» с двумя ASCII-схемами, «Принципы», «Тестируемость» с примерами TypeScript, «Связи», «Отклоненные трактовки». Раздел «Going deeper» оформить так:

```markdown
## Глубже

1. Как углублять группу модулей с учетом зависимостей, `${CLAUDE_PLUGIN_ROOT}/skills/codebase-design/DEEPENING.md`.
2. Как сравнить несколько вариантов интерфейса параллельными субагентами, `${CLAUDE_PLUGIN_ROOT}/skills/codebase-design/DESIGN-IT-TWICE.md`.
```

- [ ] **Step 5: Написать скилл `codebase-design`**

`skills/codebase-design/SKILL.md`:

```markdown
---
name: codebase-design
description: Проектируешь модуль, интерфейс или шов, делаешь код тестируемым. Глубокие модули, тест удаления, адаптеры.
---

Адаптировано из mattpocock/skills (MIT), `skills/engineering/codebase-design/SKILL.md`.

Прочитай `${CLAUDE_PLUGIN_ROOT}/refs/codebase-design.md` и проектируй в его словаре. Углубление с учетом зависимостей в `DEEPENING.md` рядом, сравнение вариантов интерфейса в `DESIGN-IT-TWICE.md` рядом.
```

`ADAPTED` для этого файла не нужен, атрибуция в нем есть, но его источник совпадает с ref. `DEEPENING.md` и `DESIGN-IT-TWICE.md` это переводы одноименных файлов по правилам выше. Ссылки `[SKILL.md](SKILL.md)` в них заменить на `${CLAUDE_PLUGIN_ROOT}/refs/codebase-design.md`, ссылки друг на друга оставить относительными.

- [ ] **Step 6: Написать скилл `writing-for-agents`**

`skills/writing-for-agents/SKILL.md` начинается так:

```markdown
---
name: writing-for-agents
description: Правишь CLAUDE.md, AGENTS.md или документ для агента. Для скиллов используй superpowers writing-skills.
---

Адаптировано из mattpocock/skills (MIT), `skills/productivity/writing-for-agents/SKILL.md`.

Когда пишешь скилл, сначала `superpowers:writing-skills`. Этот текст дополняет его правилами про указатели и нагрузку на контекст.
```

Дальше перевод тела оригинала по разделам: указатели контекста, две нагрузки, иерархия информации, шаги и критерии завершения, когда делить, ведущие слова, прополка. `SKILL-MECHANICS.md` это перевод одноименного файла. Ссылки на `SKILL.md` внутри остаются относительными.

- [ ] **Step 7: Дополнить `/agent-lint`**

В `commands/agent-lint.md` после пункта 3 списка шагов:

```markdown
4. После agnix смысловой проход по правилам `${CLAUDE_PLUGIN_ROOT}/skills/writing-for-agents/SKILL.md` для каждого CLAUDE.md, AGENTS.md, описания скилла и команды в пути. Ищи слабые формулировки указателей, лишнее в постоянно загруженном контексте, дубли смысла, запреты без позитивной цели, инструкции, которые модель выполняет и так.
```

В раздел «Вывод» последним пунктом:

```markdown
4. Находки смыслового прохода отдельным блоком после agnix, в том же формате `файл:строка` и суть одной фразой. Не больше 10.
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_texts -v`
Expected: PASS. Если `test_no_yo_and_no_dashes_in_prose` падает на переводе, переписать фразу, а не глушить тест.

- [ ] **Step 9: Stage and hand off commit**

```bash
git add refs/codebase-design.md skills/codebase-design skills/writing-for-agents commands/agent-lint.md tests/test_texts.py
```

Человеку: `! git commit -m "feat: adapt codebase-design and writing-for-agents from mattpocock/skills"`

---

### Task 10: `/grill` и `/handoff`

**Files:**
- Create: `refs/grilling.md`, `commands/grill.md`, `commands/handoff.md`
- Modify: `tests/test_texts.py` (дополнить `ADAPTED`)

**Interfaces:**
- Produces: `${CLAUDE_PLUGIN_ROOT}/refs/grilling.md` для Task 11.

- [ ] **Step 1: Write the failing test**

В `ADAPTED` добавить:

```python
    "refs/grilling.md": "skills/productivity/grilling/SKILL.md",
    "commands/handoff.md": "skills/productivity/handoff/SKILL.md",
```

Новый тест:

```python
    def test_new_commands_are_manual_only(self) -> None:
        for name in ("grill.md", "handoff.md", "architecture.md"):
            path = os.path.join(ROOT, "commands", name)
            if not os.path.exists(path):
                self.fail("нет %s" % name)
            with open(path, encoding="utf-8") as f:
                self.assertIn("disable-model-invocation: true", f.read(), name)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_texts -v`
Expected: FAIL с `FileNotFoundError` на `refs/grilling.md` и `нет grill.md`. Падение по `architecture.md` закроет Task 11.

- [ ] **Step 3: Write the files**

`refs/grilling.md`:

````markdown
# Допрос по плану

Адаптировано из mattpocock/skills (MIT), `skills/productivity/grilling/SKILL.md`.

Допрашивай человека, пока не придете к общему пониманию. Держи в голове дерево решений, где каждое решение тянет за собой зависимые.

## Раунды

1. Фронтир это все решения, у которых предпосылки уже решены. Это вопросы, которые можно задать сейчас, не угадывая ответы на другие.
2. Задавай весь фронтир одним раундом. Каждый вопрос с номером и твоим рекомендуемым ответом. Потом жди ответов.
3. Вопрос, ответ на который зависит от другого открытого вопроса этого раунда, уходит в следующий раунд.
4. После ответов пересчитай фронтир и задай следующий раунд.

Формат раунда.

```
**В1. <заголовок>.** <суть вопроса, варианты, если есть>

Рекомендую. <твой ответ и почему одной фразой>

---

**В2. <заголовок>.** <суть вопроса>

Рекомендую. <ответ>
```

## Факты и решения

1. Факты ищешь ты, а не человек. Нужен факт из кода, файлов или инструментов, найди сам или отправь субагента. Не спрашивай то, что можно посмотреть.
2. Пока субагент ищет, задавай вопросы фронтира, которые от его находки не зависят.
3. Решения принимает человек. Каждое выносишь ему и ждешь ответа.

## Конец

Допрос закончен, когда фронтир пуст. Все ветки дерева пройдены, ничего не принято молча. До подтверждения человека, что понимание общее, ничего не делай.
````

`commands/grill.md`:

```markdown
---
description: Допрос по плану, решению или идее раундами с рекомендуемым ответом на каждый вопрос.
argument-hint: [тема]
disable-model-invocation: true
---

# Допрос

1. Тема из `$ARGUMENTS`. Пусто, бери план или решение из текущего разговора. Нет и его, спроси одной фразой, что допрашиваем.
2. Веди допрос по `${CLAUDE_PLUGIN_ROOT}/refs/grilling.md`.
3. В конце список принятых решений по пунктам, без пересказа вопросов.

## Стиль

Правила из `${CLAUDE_PLUGIN_ROOT}/refs/style.md`.
```

`commands/handoff.md`:

```markdown
---
description: Сжать текущую сессию в документ для следующей. Ссылки вместо копий, без секретов.
argument-hint: [для чего следующая сессия]
disable-model-invocation: true
---

# Передача сессии

Адаптировано из mattpocock/skills (MIT), `skills/productivity/handoff/SKILL.md`.

1. Файл `${TMPDIR:-/tmp}/handoff-<YYYYMMDD-HHMM>.md`, не в репозиторий. В конце напечатай полный путь.
2. `$ARGUMENTS` это задача следующей сессии. Отбирай под нее, остальное выкидывай.
3. Разделы.
   1. Цель и где остановились, 2 или 3 предложения.
   2. Принятые решения и почему.
   3. Что дальше, по шагам.
   4. Ловушки, которые уже нашли.
   5. Какие скиллы и команды вызвать следующей сессии.
4. Что уже лежит в спеках, планах, коммитах, MR и тикетах, не копируй. Дай путь или ссылку.
5. Ключи, пароли, токены, персональные данные убери.

## Стиль

Правила из `${CLAUDE_PLUGIN_ROOT}/refs/style.md`.
```

- [ ] **Step 4: Run tests**

Run: `python3 -m unittest tests.test_texts -v`
Expected: FAIL только `test_new_commands_are_manual_only` с `нет architecture.md`, остальное PASS.

- [ ] **Step 5: Stage and hand off commit**

```bash
git add refs/grilling.md commands/grill.md commands/handoff.md tests/test_texts.py
```

Человеку: `! git commit -m "feat: add grill and handoff commands"`

---

### Task 11: `/architecture`

**Files:**
- Create: `commands/architecture.md`, `refs/architecture-report.md`
- Modify: `tests/test_texts.py` (дополнить `ADAPTED`)

**Interfaces:**
- Consumes: `refs/codebase-design.md` (Task 9), `refs/grilling.md` (Task 10), `/tmp/aihero/engineering/improve-codebase-architecture/HTML-REPORT.md` (скачан в Task 9).

- [ ] **Step 1: Write the failing test**

В `ADAPTED` добавить:

```python
    "commands/architecture.md": "skills/engineering/improve-codebase-architecture/SKILL.md",
    "refs/architecture-report.md": "skills/engineering/improve-codebase-architecture/HTML-REPORT.md",
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_texts -v`
Expected: FAIL в `test_adapted_files_credit_source` и `test_new_commands_are_manual_only`.

- [ ] **Step 3: Write `refs/architecture-report.md`**

Перевод `HTML-REPORT.md` по правилам перевода из Task 9. HTML, CSS и Mermaid в блоках кода не меняются. Подписи в шаблоне (`Files`, `Problem`, `Solution`, `Benefits`, `Before`, `After`, `Strong`, `Worth exploring`, `Speculative`, `Top recommendation`) перевести: Файлы, Проблема, Решение, Выгода, До, После, Сильно, Стоит изучить, Спекулятивно, Главная рекомендация. Первая строка после заголовка атрибуция.

- [ ] **Step 4: Write `commands/architecture.md`**

```markdown
---
description: Найти в коде места для углубления модулей, показать HTML-отчет и разобрать выбранного кандидата допросом.
argument-hint: [путь]
disable-model-invocation: true
---

# Архитектура кода

Адаптировано из mattpocock/skills (MIT), `skills/engineering/improve-codebase-architecture/SKILL.md`.

Сначала прочитай `${CLAUDE_PLUGIN_ROOT}/refs/codebase-design.md`. Говори только его словами. Модуль, интерфейс, глубина, шов, адаптер, рычаг, локальность.

## 1. Где смотреть

1. `$ARGUMENTS` путь, смотри только его.
2. Пусто. Горячие места по `git log --since=3.months --name-only --format=` сначала, они окупят углубление быстрее всего. Изменения разбросаны, расширь охват.
3. Есть `GLOSSARY.md` или `docs/adr/`, прочитай. Названия бери из глоссария. ADR не оспаривай, если трение не настолько сильное, чтобы его пересмотреть. Сам эти файлы не создавай.

## 2. Обход

Отправь субагента обходить код без жестких эвристик. Пусть отмечает трение.

1. Где для понимания одного понятия приходится прыгать по многим мелким модулям.
2. Где модуль мелкий, интерфейс почти такой же сложный, как реализация.
3. Где чистые функции вынесены ради тестов, а баги живут в том, как их вызывают.
4. Где связанные модули протекают через швы.
5. Что не покрыто тестами или трудно тестируется через текущий интерфейс.

К каждому подозрению тест удаления. Удаление собирает сложность в одном месте, это сигнал.

## 3. Отчет

1. HTML по `${CLAUDE_PLUGIN_ROOT}/refs/architecture-report.md` в `${TMPDIR:-/tmp}/architecture-<YYYYMMDD-HHMM>.html`, не в репозиторий. Открой через `open` и напечатай путь.
2. У кандидата файлы, проблема, решение, выгода в терминах рычага и локальности, схема до и после, сила рекомендации.
3. В конце главная рекомендация и почему с нее.
4. Интерфейсы пока не предлагай. Спроси, какого кандидата разобрать.

## 4. Разбор

1. Веди допрос по выбранному кандидату по `${CLAUDE_PLUGIN_ROOT}/refs/grilling.md`. Ограничения, зависимости, форма углубленного модуля, что за швом, какие тесты останутся.
2. Нужны варианты интерфейса, сделай их по `${CLAUDE_PLUGIN_ROOT}/skills/codebase-design/DESIGN-IT-TWICE.md`.
3. Человек отверг кандидата с весомой причиной и в проекте есть `docs/adr/`, предложи записать ADR, чтобы следующий обход не предлагал то же самое.

## Стиль

Правила из `${CLAUDE_PLUGIN_ROOT}/refs/style.md`. HTML-отчет на русском по тем же правилам.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_texts -v`
Expected: PASS, все тесты.

- [ ] **Step 6: Stage and hand off commit**

```bash
git add commands/architecture.md refs/architecture-report.md tests/test_texts.py
```

Человеку: `! git commit -m "feat: add architecture command adapted from improve-codebase-architecture"`

---

### Task 12: `/review` и `/check` под новые стеки

**Files:**
- Modify: `commands/review.md` (раздел «Что собрать», пункт 4), `commands/check.md` (раздел «Что запускаем»)
- Test: `tests/test_texts.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_review_and_check_cover_stacks(self) -> None:
        with open(os.path.join(ROOT, "commands", "review.md"), encoding="utf-8") as f:
            review = f.read()
        for name in ("stack-typescript.md", "stack-node.md", "stack-python.md", "stack-docker.md", "stack-nginx.md",
                     "codebase-design.md"):
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/refs/" + name, review, name)
        with open(os.path.join(ROOT, "commands", "check.md"), encoding="utf-8") as f:
            check = f.read()
        for word in ("ruff check", "pytest", "hadolint", "docker compose", "nginx -t", "biome", "oxlint"):
            self.assertIn(word, check, word)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_texts -v`
Expected: FAIL в `test_review_and_check_cover_stacks`.

- [ ] **Step 3: Edit `/review`**

В `commands/review.md` пункт 4 раздела «Что собрать» заменить целиком:

```markdown
4. Чеклисты по стеку. Читай только то, что задел дифф.
   1. В диффе `.tsx`, `.jsx` или импорты из `react`, прочитай `${CLAUDE_PLUGIN_ROOT}/refs/review-react.md`.
   2. В диффе `@nestjs/`, `prisma`, `*.resolver.ts`, `*.module.ts`, `schema.prisma`, прочитай `${CLAUDE_PLUGIN_ROOT}/refs/review-nest.md`.
   3. В диффе `.ts` или `.tsx`, прочитай `${CLAUDE_PLUGIN_ROOT}/refs/stack-typescript.md`.
   4. Серверный код не на React с импортами `node:`, `express`, `fastify`, `koa` или обращениями к `process.`, прочитай `${CLAUDE_PLUGIN_ROOT}/refs/stack-node.md`. Nest получает и его, и чеклист Nest.
   5. В диффе `.py`, прочитай `${CLAUDE_PLUGIN_ROOT}/refs/stack-python.md`.
   6. В диффе `Dockerfile*`, `*.Dockerfile`, `compose*.yml`, `docker-compose*.yml`, прочитай `${CLAUDE_PLUGIN_ROOT}/refs/stack-docker.md`.
   7. В диффе `.conf` в каталогах `nginx`, `conf.d`, `sites-*` или с именем `nginx*.conf`, прочитай `${CLAUDE_PLUGIN_ROOT}/refs/stack-nginx.md`.
   8. Дифф добавляет модуль или меняет экспортируемый интерфейс, прочитай `${CLAUDE_PLUGIN_ROOT}/refs/codebase-design.md` и добавь ось дизайна модулей. Иначе не читай.
   9. Всегда прочитай `${CLAUDE_PLUGIN_ROOT}/refs/review-shared.md`.
```

В разделе «Формат отчета» метки дополнить меткой `[дизайн]`, она идет после `[архитектура]`.

- [ ] **Step 4: Edit `/check`**

В `commands/check.md` раздел «Что запускаем» заменить целиком:

```markdown
## Что запускаем

1. Затронутые файлы. `git diff --name-only <база>...HEAD` и `git status --porcelain`, база из `$ARGUMENTS` или `origin/HEAD`. Нет изменений, проверяй весь проект.
2. JS и TS.
   1. Менеджер пакетов по lock-файлу в корне. `pnpm-lock.yaml` это pnpm, `yarn.lock` это yarn, `package-lock.json` это npm, `bun.lockb` это bun.
   2. Для каждого файла ближайший вверх `package.json`, это затронутый пакет. Нет изменений, все пакеты из workspace.
   3. По каждому пакету скрипты из его `package.json` в таком порядке. `lint`. `typecheck`, иначе `type-check`, иначе `tsc --noEmit` при `tsconfig.json`. `test` без watch, для vitest `-- --run`.
   4. Нет скрипта `lint`, но есть `biome.json`, запусти `biome check`. Есть `.oxlintrc.json`, запусти `oxlint`.
   5. Есть `schema.prisma` в затронутом пакете, `prisma validate`.
   6. Монорепо на turbo и затронуто много пакетов, можно одной командой `pnpm turbo run lint typecheck test --filter=...[<база>]`.
3. Python. Для каждого `.py` ближайший вверх `pyproject.toml`.
   1. Раннер по lock-файлу. `uv.lock` это `uv run`, `poetry.lock` это `poetry run`, иначе бинари из `.venv/bin`.
   2. `ruff check`, если ruff настроен в проекте.
   3. pyright при `pyrightconfig.json` или `[tool.pyright]`, mypy при `mypy.ini` или `[tool.mypy]`.
   4. `pytest -q`. Код 5, тесты не найдены, это не падение.
4. Docker.
   1. `hadolint` по каждому измененному Dockerfile. Нет hadolint, одна строка с подсказкой `brew install hadolint`.
   2. `docker compose -f <база> -f <файл> config -q` по каждому измененному compose-файлу. Override проверяй поверх базового файла рядом.
5. nginx. По каждому измененному конфигу `docker run --rm -v <каталог конфига>:/etc/nginx/conf.d:ro nginx:<версия из FROM ближайшего Dockerfile, иначе alpine> nginx -t`. Для главного `nginx.conf` монтируй его в `/etc/nginx/nginx.conf`. Ошибки `host not found in upstream` это имена сервисов compose, отфильтруй и упомяни одной строкой. Нет docker, пропусти с пометкой.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_texts -v`
Expected: PASS.

- [ ] **Step 6: Stage and hand off commit**

```bash
git add commands/review.md commands/check.md tests/test_texts.py
```

Человеку: `! git commit -m "feat: teach review and check about python, node, docker, nginx"`

---

### Task 13: шпаргалка, README, версия, финальная проверка

**Files:**
- Modify: `commands/commands.md`, `README.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (если там есть версия или описание)
- Test: `tests/test_manifest.py`

- [ ] **Step 1: Write the failing test**

В `ManifestTest`:

```python
    def test_plugin_version(self) -> None:
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as f:
            self.assertEqual(json.load(f)["version"], "0.2.0")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_manifest -v`
Expected: FAIL, `'0.1.0' != '0.2.0'`.

- [ ] **Step 3: Update manifests**

`.claude-plugin/plugin.json`: `"version": "0.2.0"`, `"description": "Ревью, описание MR и PR, отработка ревью, учет времени, проверки и защитные хуки для TS, Node.js, Python, Docker и nginx"`. Если в `marketplace.json` есть то же описание или версия, привести к тем же значениям.

- [ ] **Step 4: Update `/commands`**

В `commands/commands.md` в блоке формата после группы «Проверки» добавить:

```
Обдумать
/grill [тема]  допрос по плану
/architecture [путь]  углубление модулей
/handoff [задача]  передача в новую сессию
```

Пункт 4.2 заменить на:

```markdown
   2. Выключатели `DEVKIT_ACTIVITY DEVKIT_NOTIFY DEVKIT_GUARD DEVKIT_FORMAT DEVKIT_TSC DEVKIT_TYPES`, значение 0 выключает. `DEVKIT_TESTS=1` включает тесты на Stop.
```

Новым пунктом 6:

```markdown
6. Скиллы devkit из `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md` одной строкой через пробел, они срабатывают сами.
```

- [ ] **Step 5: Update README**

В таблицу команд после `/check`:

```markdown
| `/grill [тема]` | допрос по плану раундами с рекомендуемыми ответами |
| `/architecture [путь]` | HTML-отчет с кандидатами на углубление модулей и разбор выбранного |
| `/handoff [задача]` | документ для следующей сессии в `$TMPDIR` |
```

Строки хуков `stop`, `guard_bash`, `format_edit` заменить:

```markdown
| stop | Stop | tsc и pyright/mypy по правленым файлам, тесты по флагу, уведомление о готовности | `DEVKIT_TSC=0`, `DEVKIT_TYPES=0`, `DEVKIT_TESTS=1`, `DEVKIT_NOTIFY=0` |
| guard_bash | PreToolUse Bash | блок rm -rf, commit, push, reset --hard, миграций с потерей данных, удаления томов docker, публикации пакетов | `DEVKIT_GUARD=0` |
| format_edit | PostToolUse Edit Write | biome или prettier, oxlint, eslint для JS и TS, ruff для Python, hadolint, compose config, gixy | `DEVKIT_FORMAT=0` |
```

После таблицы хуков новые разделы:

~~~markdown
Инструменты запускаются, только если они настроены в проекте или установлены. Для Docker и nginx поставь их сам.

```bash
brew install hadolint
pipx install gixy-ng
```

## Скиллы

Срабатывают сами по ситуации. `typescript`, `node`, `python`, `docker`, `nginx` ведут на правила в `refs/stack-*.md`, те же правила читает `/review`. `codebase-design` про глубокие модули и швы. `writing-for-agents` про CLAUDE.md и AGENTS.md.

`/grill`, `/handoff`, `/architecture`, `codebase-design` и `writing-for-agents` адаптированы из [mattpocock/skills](https://github.com/mattpocock/skills) (MIT).
~~~

- [ ] **Step 6: Full verification**

Run: `./tests/run.sh`
Expected: PASS, весь набор, 0 failures.

Run: `npx -y agnix .`
Expected: 0 ошибок. Предупреждения прочитать и исправить, если они про новые файлы.

- [ ] **Step 7: Stage and hand off commit**

```bash
git add commands/commands.md README.md .claude-plugin tests/test_manifest.py
```

Человеку: `! git commit -m "docs: document stacks, skills and switches, bump to 0.2.0"`

- [ ] **Step 8: Ручная проверка после переустановки (делает человек)**

1. `claude plugin marketplace update devkit` и перезапуск Claude Code.
2. В списке скиллов видны `devkit:typescript`, `devkit:python`, `devkit:docker`, `devkit:nginx`, `devkit:node`, `devkit:codebase-design`, `devkit:writing-for-agents`. `/grill`, `/handoff`, `/architecture` в списке скиллов не видны, но вызываются вручную.
3. В проекте с `[tool.ruff]` правка `.py` с неиспользуемым импортом дает фидбек ruff.
4. В `calendar-app` правка `docker-compose.override.yml` с битым отступом дает фидбек compose, исправная правка проходит молча.
