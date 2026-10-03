# devkit 0.3: выбор, детект и контроль архитектуры. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Команда `/arch init | detect | check`, каталог из 8 архитектур React и NestJS и контракт в проекте (`ARCHITECTURE.md`, dependency-cruiser с baseline, steiger для FSD), по которому проект строго держит архитектуру.

**Architecture:** Знания лежат в `refs/arch/<id>.md` с одинаковыми 8 разделами, правила импортов в `refs/arch/depcruise/<id>.json`. Два stdlib-скрипта. `scripts/arch_contract.py` собирает самодостаточный `.dependency-cruiser.cjs`, считает baseline и долг steiger и пишет скрипт `lint:arch`. `scripts/arch_detect.py` угадывает архитектуру по каталогам и импортам. Команда `/arch` склеивает их и спрашивает человека. Скилл `arch-rules`, `/review` и `/check` читают контракт проекта.

**Tech Stack:** Python 3.9.6 stdlib и `unittest`, формат плагина Claude Code (`commands/`, `skills/`), в проекте пользователя dependency-cruiser 18 и steiger 0.7 с `@feature-sliced/steiger-plugin`.

**Spec:** `docs/specs/2026-10-03-devkit-arch-design.md`

## Global Constraints

- Python 3.9.6: нет `match`, нет `X | Y` и `list[str]` в аннотациях, нет `tomllib`. Типы из `typing`. Только stdlib.
- Ни одной новой записи в `hooks.json`.
- Ничего не ставится в проект пользователя и не перезаписывается без «да» человека.
- Тексты в `commands/`, `refs/` (включая `refs/arch/`), `skills/` по `refs/style.md`: без тире и ` - ` как паузы, без `ё`, без `;`, двоеточие только в `файл:строка` и времени, без эмодзи. Это проверяет `tests/test_texts.py`.
- Описание каждого `SKILL.md` до 120 символов, одна строка, без двоеточия.
- Имена людей в ref только с подтвержденным источником. Климова и ThePrimeagen в ref не называть.
- Шаблоны правил это JSON с токеном `__ROOT__/`, без него правило не привязано к корню. Набор правил проверен на dependency-cruiser 18.5.0, текст правил из Task 1 переносится дословно.
- `git commit` блокирует собственный `guard_bash`. Исполнитель делает `git add` и выдает человеку готовую команду `! git commit -m "..."`. Сам не коммитит и сторож не выключает.
- Полный прогон: `./tests/run.sh`. Отдельный файл: `python3 -m unittest tests.test_arch_contract -v` из корня репозитория.
- Живой тест правил: `DEVKIT_DEPCRUISE=<путь к node_modules/.bin/depcruise> python3 -m unittest tests.test_arch_live -v`. Без переменной он пропускается.

## Review Focus

1. Проект без `src`, корень исходников `.`. Правила должны стать `^features/`, а не `^./features/` или `^/features/`, скрипт `depcruise . --ignore-known`, детект берет корень пакета. Тесты в Task 1 и Task 4.
2. Корень с символами регулярки (`my.app/src`). Точка экранируется, JSON остается валидным. Тест в Task 1.
3. `tsconfig.json` с комментариями и висячими запятыми, как его пишут Vite и Nest CLI. Детект не падает и резолвит алиас `@/`. Тест в Task 4.
4. `pnpm-workspace.yaml` с globs в кавычках и с отрицанием `!**/test/**`. Отрицание пропускается, пакеты находятся. Тест в Task 4.
5. Новый проект без нарушений. Файла baseline нет, `--ignore-known` падает с `Can't open '.dependency-cruiser-known-violations.json'`. `init` пишет `[]`, `count` на пустом вводе дает 0. Тесты в Task 1 и Task 5.

---

### Task 1: шаблоны правил и `arch_contract.py`

**Files:**
- Create: `refs/arch/depcruise/base.json`, `react-fsd.json`, `react-feod.json`, `react-evolution.json`, `react-evolution.medium.json`, `react-feature.json`, `react-clean.json`, `nest-standard.json`, `nest-modular-clean.json`, `nest-ddd-cqrs.json`
- Create: `scripts/arch_contract.py`
- Test: `tests/test_arch_contract.py`, `tests/test_arch_live.py`

**Interfaces:**
- Consumes: ничего.
- Produces:
  - `arch_contract.TEMPLATES: str`, путь к `refs/arch/depcruise`.
  - `arch_contract.ARCHS: List[str]`, 8 id в порядке `react-fsd react-feod react-evolution react-feature react-clean nest-standard nest-modular-clean nest-ddd-cqrs`.
  - `arch_contract.render_depcruise(arch: str, variant: Optional[str] = None, root: str = "src", tsconfig: Optional[str] = None, templates: str = TEMPLATES) -> str`, текст `.dependency-cruiser.cjs`. Неизвестный `arch` или вариант дает `FileNotFoundError`.
  - `arch_contract.config_json(cjs: str) -> Dict[str, Any]`, обратный разбор текста из `render_depcruise`, для тестов и `/arch`.
  - `arch_contract.count_violations(text: str) -> int`. Пустой текст 0, не список `ValueError`.
  - `arch_contract.steiger_debt(text: str) -> List[str]`, отсортированные `ruleName` с `severity == "error"`.
  - `arch_contract.lint_script(arch: str, root: str = "src", evo: bool = False) -> str`.
  - CLI `python3 scripts/arch_contract.py depcruise --arch <id> [--variant v] [--root src] [--tsconfig f]`, `count` (stdin), `steiger-debt` (stdin), `lint-script --arch <id> [--root src] [--evo]`. Ошибка дает код 2 и строку в stderr.

- [ ] **Step 1: Создай шаблоны правил**

Тексты ниже проверены на dependency-cruiser 18.5.0. Перенеси дословно, по файлу на блок.

`refs/arch/depcruise/base.json`:

```json
{
  "forbidden": [
    {"name": "no-circular", "severity": "warn", "from": {}, "to": {"circular": true}, "comment": "Цикл импортов"},
    {"name": "no-orphans", "severity": "warn", "from": {"orphan": true, "pathNot": ["\\.d\\.ts$", "(^|/)\\.[^/]+\\.(js|cjs|mjs|ts|json)$", "\\.(spec|test)\\.(ts|tsx|js|jsx)$", "(^|/)(main|index)\\.(ts|tsx)$"]}, "to": {}, "comment": "Файл никто не импортирует"}
  ],
  "options": {"doNotFollow": {"path": "node_modules"}, "exclude": {"path": "(^|/)(node_modules|dist|build|\\.next|coverage)/"}, "tsPreCompilationDeps": true}
}
```

`refs/arch/depcruise/react-fsd.json`:

```json
{
  "forbidden": [
    {"name": "fsd-layers-pages", "severity": "error", "from": {"path": "^__ROOT__/pages/"}, "to": {"path": "^__ROOT__/(app)/"}, "comment": "Слой импортирует только слои ниже"},
    {"name": "fsd-layers-widgets", "severity": "error", "from": {"path": "^__ROOT__/widgets/"}, "to": {"path": "^__ROOT__/(app|pages)/"}, "comment": "Слой импортирует только слои ниже"},
    {"name": "fsd-layers-features", "severity": "error", "from": {"path": "^__ROOT__/features/"}, "to": {"path": "^__ROOT__/(app|pages|widgets)/"}, "comment": "Слой импортирует только слои ниже"},
    {"name": "fsd-layers-entities", "severity": "error", "from": {"path": "^__ROOT__/entities/"}, "to": {"path": "^__ROOT__/(app|pages|widgets|features)/"}, "comment": "Слой импортирует только слои ниже"},
    {"name": "fsd-layers-shared", "severity": "error", "from": {"path": "^__ROOT__/shared/"}, "to": {"path": "^__ROOT__/(app|pages|widgets|features|entities)/"}, "comment": "Слой импортирует только слои ниже"},
    {"name": "fsd-cross-slice", "severity": "error", "from": {"path": "^__ROOT__/(pages|widgets|features|entities)/([^/]+)/"}, "to": {"path": "^__ROOT__/$1/", "pathNot": ["^__ROOT__/$1/$2/", "^__ROOT__/entities/[^/]+/@x/"]}, "comment": "Слайс не импортирует соседа по слою, у entities только через @x"},
    {"name": "fsd-public-api", "severity": "error", "from": {"path": "^__ROOT__/([^/]+)/([^/]+)/"}, "to": {"path": "^__ROOT__/(pages|widgets|features|entities)/[^/]+/.+", "pathNot": ["^__ROOT__/$1/$2/", "^__ROOT__/(pages|widgets|features|entities)/[^/]+/index\\.(ts|tsx|js|jsx)$", "^__ROOT__/entities/[^/]+/@x/"]}, "comment": "Снаружи слайса только через index"}
  ]
}
```

`refs/arch/depcruise/react-feod.json`:

```json
{
  "forbidden": [
    {"name": "feod-common-isolated", "severity": "error", "from": {"path": "^__ROOT__/common/"}, "to": {"path": "^__ROOT__/(app|pages|modules|global)/"}, "comment": "common не импортирует код проекта"},
    {"name": "feod-modules-up", "severity": "error", "from": {"path": "^__ROOT__/modules/"}, "to": {"path": "^__ROOT__/(app|pages)/"}, "comment": "Модули не импортируют pages и app"},
    {"name": "feod-pages-up", "severity": "error", "from": {"path": "^__ROOT__/pages/"}, "to": {"path": "^__ROOT__/app/"}, "comment": "Из app никто не импортирует"},
    {"name": "feod-no-global-import", "severity": "error", "from": {"path": "^__ROOT__/", "pathNot": "^__ROOT__/global/"}, "to": {"path": "^__ROOT__/global/"}, "comment": "global доступен без импорта"},
    {"name": "feod-public-api", "severity": "error", "from": {"path": "^__ROOT__/([^/]+)/([^/]+)/"}, "to": {"path": "^__ROOT__/modules/[^/]+/.+", "pathNot": ["^__ROOT__/$1/$2/", "^__ROOT__/modules/[^/]+/index\\.(ts|tsx|js|jsx)$"]}, "comment": "Снаружи модуля только через index"}
  ]
}
```

`refs/arch/depcruise/react-evolution.json`:

```json
{
  "forbidden": [
    {"name": "ed-no-app", "severity": "error", "from": {"path": "^__ROOT__/(features|services|shared)/"}, "to": {"path": "^__ROOT__/app/"}, "comment": "Из app никто не импортирует"},
    {"name": "ed-no-features", "severity": "error", "from": {"path": "^__ROOT__/(services|shared)/"}, "to": {"path": "^__ROOT__/features/"}, "comment": "services и shared не импортируют features"},
    {"name": "ed-shared-no-services", "severity": "error", "from": {"path": "^__ROOT__/shared/"}, "to": {"path": "^__ROOT__/services/"}, "comment": "shared не импортирует services"},
    {"name": "ed-public-api", "severity": "error", "from": {"path": "^__ROOT__/([^/]+)/([^/]+)/"}, "to": {"path": "^__ROOT__/(features|services)/[^/]+/.+", "pathNot": ["^__ROOT__/$1/$2/", "^__ROOT__/(features|services)/[^/]+/index\\.(ts|tsx|js|jsx)$"]}, "comment": "Снаружи модуля только через index"}
  ]
}
```

`refs/arch/depcruise/react-evolution.medium.json`:

```json
{
  "forbidden": [
    {"name": "ed-cross-feature", "severity": "error", "from": {"path": "^__ROOT__/features/([^/]+)/"}, "to": {"path": "^__ROOT__/features/", "pathNot": "^__ROOT__/features/$1/"}, "comment": "В medium фича не импортирует фичу"}
  ]
}
```

`refs/arch/depcruise/react-feature.json`:

```json
{
  "forbidden": [
    {"name": "feature-cross", "severity": "error", "from": {"path": "^__ROOT__/features/([^/]+)/"}, "to": {"path": "^__ROOT__/features/", "pathNot": "^__ROOT__/features/$1/"}, "comment": "Фича не импортирует фичу, композиция в app"},
    {"name": "feature-no-app", "severity": "error", "from": {"path": "^__ROOT__/features/"}, "to": {"path": "^__ROOT__/app/"}, "comment": "Фича не импортирует app"},
    {"name": "feature-shared-up", "severity": "error", "from": {"path": "^__ROOT__/(components|hooks|lib|utils|types|config|stores|api|assets|testing)/"}, "to": {"path": "^__ROOT__/(app|features)/"}, "comment": "Общий код не импортирует фичи и app"}
  ]
}
```

`refs/arch/depcruise/react-clean.json`:

```json
{
  "forbidden": [
    {"name": "clean-domain-inner", "severity": "error", "from": {"path": "^__ROOT__/domain/"}, "to": {"path": "^__ROOT__/(application|infrastructure|ui|presentation)/"}, "comment": "domain ни от чего не зависит"},
    {"name": "clean-domain-no-libs", "severity": "error", "from": {"path": "^__ROOT__/domain/"}, "to": {"path": "(^|node_modules/)(react|react-dom|axios|ky|@tanstack/[^/]+)(/|$)"}, "comment": "domain без React и HTTP-клиентов"},
    {"name": "clean-application-inner", "severity": "error", "from": {"path": "^__ROOT__/application/"}, "to": {"path": "^__ROOT__/(infrastructure|ui|presentation)/"}, "comment": "application видит только domain и свои порты"},
    {"name": "clean-infrastructure-no-ui", "severity": "error", "from": {"path": "^__ROOT__/infrastructure/"}, "to": {"path": "^__ROOT__/(ui|presentation)/"}, "comment": "Адаптеры не импортируют UI"}
  ]
}
```

`refs/arch/depcruise/nest-standard.json`:

```json
{
  "forbidden": [
    {"name": "nest-controller-no-orm", "severity": "error", "from": {"path": "\\.(controller|resolver)\\.ts$"}, "to": {"path": "(^|node_modules/)(@prisma/client|typeorm|mongoose|@mikro-orm/[^/]+|drizzle-orm)(/|$)"}, "comment": "Контроллер и резолвер зовут сервис, не ORM"},
    {"name": "nest-controller-no-repository", "severity": "error", "from": {"path": "\\.(controller|resolver)\\.ts$"}, "to": {"path": "\\.repository\\.ts$"}, "comment": "Контроллер и резолвер зовут сервис, не репозиторий"},
    {"name": "nest-foreign-internals", "severity": "error", "from": {"path": "^__ROOT__/([^/]+)/"}, "to": {"path": "^__ROOT__/[^/]+/.+", "pathNot": ["^__ROOT__/$1/", "\\.(module|service)\\.ts$", "/dto/", "^__ROOT__/(common|config|shared)/"]}, "comment": "У чужого модуля можно брать только module, service и dto"},
    {"name": "nest-common-no-features", "severity": "error", "from": {"path": "^__ROOT__/(common|config|shared)/"}, "to": {"path": "^__ROOT__/", "pathNot": "^__ROOT__/(common|config|shared)/"}, "comment": "common и config не импортируют модули фич"}
  ]
}
```

`refs/arch/depcruise/nest-modular-clean.json`:

```json
{
  "forbidden": [
    {"name": "nmc-public-api", "severity": "error", "from": {"path": "^__ROOT__/modules/([^/]+)/"}, "to": {"path": "^__ROOT__/modules/[^/]+/.+", "pathNot": ["^__ROOT__/modules/$1/", "^__ROOT__/modules/[^/]+/index\\.ts$"]}, "comment": "Чужой модуль только через index.ts"},
    {"name": "nmc-domain-inner", "severity": "error", "from": {"path": "^__ROOT__/modules/[^/]+/domain/"}, "to": {"path": "^__ROOT__/modules/[^/]+/(application|infrastructure|presentation)/"}, "comment": "domain ни от чего не зависит"},
    {"name": "nmc-domain-no-framework", "severity": "error", "from": {"path": "^__ROOT__/modules/[^/]+/domain/"}, "to": {"path": ["(^|node_modules/)@nestjs/[^/]+(/|$)", "(^|node_modules/)(@prisma/client|typeorm|mongoose|@mikro-orm/[^/]+|drizzle-orm)(/|$)"]}, "comment": "domain без Nest и ORM"},
    {"name": "nmc-application-inner", "severity": "error", "from": {"path": "^__ROOT__/modules/[^/]+/application/"}, "to": {"path": "^__ROOT__/modules/[^/]+/(infrastructure|presentation)/"}, "comment": "application видит только domain"},
    {"name": "nmc-presentation-no-infrastructure", "severity": "error", "from": {"path": "^__ROOT__/modules/[^/]+/presentation/"}, "to": {"path": "^__ROOT__/modules/[^/]+/infrastructure/"}, "comment": "presentation зовет application"},
    {"name": "nmc-orm-in-infrastructure", "severity": "error", "from": {"path": "^__ROOT__/", "pathNot": ["^__ROOT__/modules/[^/]+/infrastructure/", "^__ROOT__/(shared|database|prisma)/"]}, "to": {"path": "(^|node_modules/)(@prisma/client|typeorm|mongoose|@mikro-orm/[^/]+|drizzle-orm)(/|$)"}, "comment": "ORM только в infrastructure"},
    {"name": "nmc-shared-no-modules", "severity": "error", "from": {"path": "^__ROOT__/shared/"}, "to": {"path": "^__ROOT__/modules/"}, "comment": "shared не импортирует модули"}
  ]
}
```

`refs/arch/depcruise/nest-ddd-cqrs.json`:

```json
{
  "forbidden": [
    {"name": "ddd-context-contracts", "severity": "error", "from": {"path": "^__ROOT__/contexts/([^/]+)/"}, "to": {"path": "^__ROOT__/contexts/[^/]+/", "pathNot": ["^__ROOT__/contexts/$1/", "^__ROOT__/contexts/[^/]+/contracts/"]}, "comment": "Чужой контекст только через contracts"},
    {"name": "ddd-domain-inner", "severity": "error", "from": {"path": "^__ROOT__/contexts/[^/]+/domain/"}, "to": {"path": "^__ROOT__/contexts/[^/]+/(application|infrastructure|presentation)/"}, "comment": "domain ни от чего не зависит"},
    {"name": "ddd-domain-no-framework", "severity": "error", "from": {"path": "^__ROOT__/contexts/[^/]+/domain/"}, "to": {"path": ["(^|node_modules/)@nestjs/[^/]+(/|$)", "(^|node_modules/)(@prisma/client|typeorm|mongoose|@mikro-orm/[^/]+|drizzle-orm)(/|$)"]}, "comment": "domain без Nest и ORM"},
    {"name": "ddd-application-inner", "severity": "error", "from": {"path": "^__ROOT__/contexts/[^/]+/application/"}, "to": {"path": "^__ROOT__/contexts/[^/]+/(infrastructure|presentation)/"}, "comment": "application видит только domain и contracts"},
    {"name": "ddd-shared-no-contexts", "severity": "error", "from": {"path": "^__ROOT__/shared/"}, "to": {"path": "^__ROOT__/contexts/"}, "comment": "shared не импортирует контексты"}
  ]
}
```

- [ ] **Step 2: Напиши падающий тест**

`tests/test_arch_contract.py`:

```python
import glob
import json
import os
import subprocess
import sys
import unittest

from tests.helpers import ROOT, SCRIPTS

sys.path.insert(0, SCRIPTS)
import arch_contract  # noqa: E402

SCRIPT = os.path.join(SCRIPTS, "arch_contract.py")


def rules(cjs: str) -> dict:
    return {r["name"]: r for r in arch_contract.config_json(cjs)["forbidden"]}


def run(args: list, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, SCRIPT] + args, input=stdin, capture_output=True, text=True, timeout=30)


class TemplatesTest(unittest.TestCase):
    def test_every_arch_has_template(self) -> None:
        names = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(arch_contract.TEMPLATES, "*.json"))}
        self.assertEqual(names, set(arch_contract.ARCHS) | {"base", "react-evolution.medium"})

    def test_rules_valid_and_bound_to_root(self) -> None:
        seen = set()
        for path in sorted(glob.glob(os.path.join(arch_contract.TEMPLATES, "*.json"))):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for rule in data["forbidden"]:
                where = "%s %s" % (os.path.basename(path), rule["name"])
                self.assertNotIn(rule["name"], seen, where)
                seen.add(rule["name"])
                self.assertIn(rule["severity"], ("error", "warn"), where)
                self.assertTrue(rule.get("comment"), where)
                self.assertNotIn("__ROOT__", json.dumps(rule).replace("__ROOT__/", ""), where)


class RenderTest(unittest.TestCase):
    def test_src_root(self) -> None:
        text = arch_contract.render_depcruise("react-fsd")
        self.assertTrue(text.startswith("// "))
        self.assertIn("module.exports = ", text)
        self.assertNotIn("__ROOT__", text)
        found = rules(text)
        self.assertEqual(found["fsd-layers-shared"]["from"]["path"], "^src/shared/")
        self.assertIn("no-circular", found)
        self.assertNotIn("tsConfig", arch_contract.config_json(text)["options"])

    def test_tsconfig(self) -> None:
        text = arch_contract.render_depcruise("react-fsd", tsconfig="tsconfig.app.json")
        self.assertEqual(arch_contract.config_json(text)["options"]["tsConfig"], {"fileName": "tsconfig.app.json"})

    def test_dot_root_drops_prefix(self) -> None:
        for root in (".", "", "./"):
            found = rules(arch_contract.render_depcruise("react-feature", root=root))
            self.assertEqual(found["feature-no-app"]["from"]["path"], "^features/", root)

    def test_root_with_regex_chars(self) -> None:
        found = rules(arch_contract.render_depcruise("react-feature", root="my.app/src/"))
        self.assertEqual(found["feature-no-app"]["from"]["path"], "^my\\.app/src/features/")

    def test_variant(self) -> None:
        self.assertNotIn("ed-cross-feature", rules(arch_contract.render_depcruise("react-evolution")))
        self.assertIn("ed-cross-feature", rules(arch_contract.render_depcruise("react-evolution", variant="medium")))

    def test_unknown(self) -> None:
        with self.assertRaises(FileNotFoundError):
            arch_contract.render_depcruise("react-mvc")
        with self.assertRaises(FileNotFoundError):
            arch_contract.render_depcruise("react-fsd", variant="medium")


class CountTest(unittest.TestCase):
    def test_count(self) -> None:
        self.assertEqual(arch_contract.count_violations(""), 0)
        self.assertEqual(arch_contract.count_violations("  \n"), 0)
        self.assertEqual(arch_contract.count_violations("[]"), 0)
        self.assertEqual(arch_contract.count_violations('[{"from": "a"}, {"from": "b"}]'), 2)
        with self.assertRaises(ValueError):
            arch_contract.count_violations("{}")

    def test_steiger_debt(self) -> None:
        text = json.dumps([
            {"ruleName": "fsd/no-segmentless-slices", "severity": "error"},
            {"ruleName": "fsd/no-segmentless-slices", "severity": "error"},
            {"ruleName": "fsd/forbidden-imports", "severity": "error"},
            {"ruleName": "fsd/insignificant-slice", "severity": "warn"},
        ])
        self.assertEqual(arch_contract.steiger_debt(text), ["fsd/forbidden-imports", "fsd/no-segmentless-slices"])
        self.assertEqual(arch_contract.steiger_debt(""), [])


class LintScriptTest(unittest.TestCase):
    def test_scripts(self) -> None:
        self.assertEqual(arch_contract.lint_script("react-fsd"), "depcruise src --ignore-known && steiger src")
        self.assertEqual(arch_contract.lint_script("nest-standard", root="."), "depcruise . --ignore-known")
        self.assertEqual(arch_contract.lint_script("react-evolution", root="src/", evo=True),
                         "depcruise src --ignore-known && edlint lint")


class CliTest(unittest.TestCase):
    def test_depcruise(self) -> None:
        proc = run(["depcruise", "--arch", "nest-standard", "--root", "src", "--tsconfig", "tsconfig.json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("nest-foreign-internals", rules(proc.stdout))

    def test_count_and_debt(self) -> None:
        self.assertEqual(run(["count"], "[{}, {}, {}]").stdout.strip(), "3")
        self.assertEqual(run(["steiger-debt"], '[{"ruleName": "fsd/x", "severity": "error"}]').stdout.strip(), "fsd/x")

    def test_lint_script(self) -> None:
        self.assertEqual(run(["lint-script", "--arch", "react-fsd"]).stdout.strip(),
                         "depcruise src --ignore-known && steiger src")

    def test_errors_exit_2(self) -> None:
        proc = run(["depcruise", "--arch", "react-mvc"])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("react-mvc", proc.stderr)
        self.assertEqual(run(["count"], "{}").returncode, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Запусти, убедись, что падает**

Run: `python3 -m unittest tests.test_arch_contract -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'arch_contract'`.

- [ ] **Step 4: Напиши `scripts/arch_contract.py`**

```python
#!/usr/bin/env python3
"""Собирает контракт архитектуры для /arch. Конфиг dependency-cruiser, счет нарушений baseline,
долг steiger и скрипт lint:arch. Только stdlib, чтобы работать без зависимостей плагина.
"""
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "refs", "arch", "depcruise")
ARCHS = ["react-fsd", "react-feod", "react-evolution", "react-feature", "react-clean",
         "nest-standard", "nest-modular-clean", "nest-ddd-cqrs"]
ROOT_TOKEN = "__ROOT__/"
EXPORT_PREFIX = "module.exports = "


def _load(name: str, templates: str) -> Dict[str, Any]:
    with open(os.path.join(templates, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def _clean_root(root: str) -> str:
    clean = root.strip()
    while clean.startswith("./"):
        clean = clean[2:]
    return clean.strip("/")


def _root_prefix(root: str) -> str:
    clean = _clean_root(root)
    if clean in ("", "."):
        return ""
    # Префикс вставляется внутрь JSON-строки, поэтому экранируем и для регулярки, и для JSON
    return json.dumps(re.escape(clean) + "/")[1:-1]


def render_depcruise(arch: str, variant: Optional[str] = None, root: str = "src",
                     tsconfig: Optional[str] = None, templates: str = TEMPLATES) -> str:
    base = _load("base", templates)
    rules = list(base["forbidden"]) + _load(arch, templates)["forbidden"]
    if variant:
        rules += _load("%s.%s" % (arch, variant), templates)["forbidden"]
    options = dict(base["options"])
    if tsconfig:
        options["tsConfig"] = {"fileName": tsconfig}
    body = json.dumps({"forbidden": rules, "options": options}, ensure_ascii=False, indent=2)
    body = body.replace(ROOT_TOKEN, _root_prefix(root))
    name = arch + ("." + variant if variant else "")
    return ("// Сгенерировано devkit /arch для %s. Правила описаны в ARCHITECTURE.md.\n"
            "/** @type {import('dependency-cruiser').IConfiguration} */\n%s%s;\n" % (name, EXPORT_PREFIX, body))


def config_json(cjs: str) -> Dict[str, Any]:
    start = cjs.index(EXPORT_PREFIX) + len(EXPORT_PREFIX)
    return json.loads(cjs[start:].rstrip().rstrip(";"))


def _json_list(text: str) -> List[Any]:
    if not text.strip():
        return []
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("ожидался JSON-список, пришел %s" % type(data).__name__)
    return data


def count_violations(text: str) -> int:
    return len(_json_list(text))


def steiger_debt(text: str) -> List[str]:
    return sorted({item["ruleName"] for item in _json_list(text)
                   if isinstance(item, dict) and item.get("severity") == "error" and item.get("ruleName")})


def lint_script(arch: str, root: str = "src", evo: bool = False) -> str:
    target = _clean_root(root) or "."
    parts = ["depcruise %s --ignore-known" % target]
    if arch == "react-fsd":
        parts.append("steiger %s" % target)
    if evo:
        parts.append("edlint lint")
    return " && ".join(parts)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    dep = sub.add_parser("depcruise")
    dep.add_argument("--arch", required=True)
    dep.add_argument("--variant")
    dep.add_argument("--root", default="src")
    dep.add_argument("--tsconfig")
    sub.add_parser("count")
    sub.add_parser("steiger-debt")
    lint = sub.add_parser("lint-script")
    lint.add_argument("--arch", required=True)
    lint.add_argument("--root", default="src")
    lint.add_argument("--evo", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "depcruise":
            sys.stdout.write(render_depcruise(args.arch, args.variant, args.root, args.tsconfig))
        elif args.command == "count":
            print(count_violations(sys.stdin.read()))
        elif args.command == "steiger-debt":
            for rule in steiger_debt(sys.stdin.read()):
                print(rule)
        else:
            print(lint_script(args.arch, args.root, args.evo))
    except FileNotFoundError as error:
        sys.stderr.write("нет шаблона %s\n" % os.path.basename(str(error.filename or error)))
        return 2
    except ValueError as error:
        sys.stderr.write("%s\n" % error)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Нюанс `test_errors_exit_2`: имя файла в `FileNotFoundError` это `.../react-mvc.json`, `basename` дает `react-mvc.json`, проверка `assertIn("react-mvc", ...)` проходит.

- [ ] **Step 5: Запусти, убедись, что проходит**

Run: `python3 -m unittest tests.test_arch_contract -v`
Expected: PASS, 15 тестов.

- [ ] **Step 6: Напиши живой тест правил**

`tests/test_arch_live.py`. Пропускается без `DEVKIT_DEPCRUISE`. По примеру на архитектуру, в каждом нарушено каждое правило, а импорты из `allowed` должны пройти.

```python
import json
import os
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import SCRIPTS

sys.path.insert(0, SCRIPTS)
import arch_contract  # noqa: E402

DEPCRUISE = os.environ.get("DEVKIT_DEPCRUISE", "")
TSCONFIG = '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}'

# arch: (файлы, вариант, правила, которые должны сработать, пары from -> to, которые не должны)
CASES = {
    "react-fsd": ({
        "src/app/index.tsx": "import {P} from '../pages/home'; export const A=P",
        "src/pages/home/index.ts": "import {W} from '@/widgets/header'; export const P=W",
        "src/widgets/header/index.ts": "import {F} from '../../features/auth'; import {deep} from '../../features/auth/model/store'; export const W=F+deep",
        "src/features/auth/index.ts": "import {C} from '../cart'; import {U} from '@/entities/user'; export const F=C+U",
        "src/features/auth/model/store.ts": "export const deep=1",
        "src/features/cart/index.ts": "export const C=1",
        "src/entities/user/index.ts": "import {O} from '../order/@x/user'; import {X} from '../order'; export const U=O+X",
        "src/entities/order/index.ts": "export const X=1",
        "src/entities/order/@x/user.ts": "export const O=1",
        "src/shared/ui/index.ts": "import {U} from '@/entities/user'; export const S=U",
    }, None, {"fsd-public-api", "fsd-cross-slice", "fsd-layers-shared"},
        {"src/entities/user/index.ts -> src/entities/order/@x/user.ts", "src/app/index.tsx -> src/pages/home/index.ts"}),
    "react-feod": ({
        "src/app/index.tsx": "import {P} from '../pages/home'; export const A=P",
        "src/pages/home/index.ts": "import {M} from '@/modules/cart'; import {D} from '@/modules/cart/model/d'; import {A} from '../../app'; export const P=M+D",
        "src/modules/cart/index.ts": "import {D} from './model/d'; import {Q} from '../user'; import {G} from '../../global/g'; export const M=D+Q+G",
        "src/modules/cart/model/d.ts": "export const D=1",
        "src/modules/user/index.ts": "import {C} from '@/common/x'; export const Q=C",
        "src/common/x.ts": "import {Q} from '../modules/user'; export const C=1",
        "src/global/g.ts": "export const G=1",
    }, None, {"feod-public-api", "feod-pages-up", "feod-no-global-import", "feod-common-isolated"},
        {"src/modules/cart/index.ts -> src/modules/user/index.ts"}),
    "react-evolution": ({
        "src/app/index.tsx": "import {T} from '@/features/tasks'; export const A=T",
        "src/features/tasks/index.ts": "import {S} from '@/services/session'; import {AU} from '../auth'; import {X} from '@/services/session/model/x'; export const T=S+AU+X",
        "src/features/auth/index.ts": "import {A} from '@/app'; export const AU=1",
        "src/services/session/index.ts": "import {T} from '@/features/tasks'; export const S=1",
        "src/services/session/model/x.ts": "export const X=1",
        "src/shared/lib/index.ts": "import {S} from '@/services/session'; export const L=S",
    }, "medium", {"ed-no-app", "ed-no-features", "ed-shared-no-services", "ed-public-api", "ed-cross-feature"},
        {"src/features/tasks/index.ts -> src/services/session/index.ts"}),
    "react-feature": ({
        "src/app/index.tsx": "import {T} from '@/features/tasks/components/list'; export const A=T",
        "src/features/tasks/components/list.tsx": "import {AU} from '@/features/auth/api/x'; import {B} from '@/components/button'; export const T=AU+B",
        "src/features/auth/api/x.ts": "import {A} from '@/app'; export const AU=1",
        "src/components/button.tsx": "import {T} from '@/features/tasks/components/list'; export const B=1",
    }, None, {"feature-cross", "feature-no-app", "feature-shared-up"},
        {"src/app/index.tsx -> src/features/tasks/components/list.tsx"}),
    "react-clean": ({
        "src/ui/page.tsx": "import {uc} from '@/application/uc'; export const P=uc",
        "src/application/uc.ts": "import {E} from '@/domain/e'; import {I} from '@/infrastructure/api'; export const uc=E+I",
        "src/domain/e.ts": "import React from 'react'; import {uc} from '@/application/uc'; export const E=1",
        "src/infrastructure/api.ts": "import {P} from '@/ui/page'; export const I=1",
    }, None, {"clean-application-inner", "clean-domain-inner", "clean-domain-no-libs", "clean-infrastructure-no-ui"},
        {"src/ui/page.tsx -> src/application/uc.ts"}),
    "nest-standard": ({
        "src/users/users.controller.ts": "import {S} from './users.service'; import {PrismaClient} from '@prisma/client'; import {R} from './users.repository'; export const C=S",
        "src/users/users.service.ts": "import {O} from '../orders/orders.service'; import {OC} from '../orders/orders.controller'; import {D} from '../orders/dto/create.dto'; import {E} from '../orders/entities/order.entity'; import {cfg} from '../config/x'; export const S=O",
        "src/users/users.repository.ts": "export const R=1",
        "src/orders/orders.service.ts": "export const O=1",
        "src/orders/orders.controller.ts": "export const OC=1",
        "src/orders/dto/create.dto.ts": "export const D=1",
        "src/orders/entities/order.entity.ts": "export const E=1",
        "src/config/x.ts": "import {S} from '../users/users.service'; export const cfg=1",
    }, None, {"nest-controller-no-orm", "nest-controller-no-repository", "nest-foreign-internals", "nest-common-no-features"},
        {"src/users/users.service.ts -> src/orders/dto/create.dto.ts", "src/users/users.service.ts -> src/orders/orders.service.ts"}),
    "nest-modular-clean": ({
        "src/modules/users/index.ts": "export * from './users.module'",
        "src/modules/users/users.module.ts": "import {C} from './presentation/c'; export const M=C",
        "src/modules/users/presentation/c.ts": "import {U} from '../application/u'; import {I} from '../infrastructure/repo'; export const C=U",
        "src/modules/users/application/u.ts": "import {E} from '../domain/e'; import {I} from '../infrastructure/repo'; import {O} from '../../orders'; import {X} from '../../orders/domain/x'; export const U=E",
        "src/modules/users/domain/e.ts": "import {Injectable} from '@nestjs/common'; import {U} from '../application/u'; export const E=1",
        "src/modules/users/infrastructure/repo.ts": "import {PrismaClient} from '@prisma/client'; export const I=1",
        "src/modules/orders/index.ts": "export const O=1",
        "src/modules/orders/domain/x.ts": "import {PrismaClient} from '@prisma/client'; export const X=1",
        "src/shared/s.ts": "import {O} from '../modules/orders'; export const S=1",
    }, None, {"nmc-public-api", "nmc-domain-inner", "nmc-domain-no-framework", "nmc-application-inner",
              "nmc-presentation-no-infrastructure", "nmc-orm-in-infrastructure", "nmc-shared-no-modules"},
        {"src/modules/users/application/u.ts -> src/modules/orders/index.ts"}),
    "nest-ddd-cqrs": ({
        "src/contexts/billing/application/h.ts": "import {E} from '../domain/e'; import {I} from '../infrastructure/r'; import {Ev} from '../../users/contracts/events'; import {UE} from '../../users/domain/user'; export const H=E",
        "src/contexts/billing/domain/e.ts": "import {Injectable} from '@nestjs/common'; import {H} from '../application/h'; export const E=1",
        "src/contexts/billing/infrastructure/r.ts": "export const I=1",
        "src/contexts/users/contracts/events.ts": "export const Ev=1",
        "src/contexts/users/domain/user.ts": "export const UE=1",
        "src/shared/s.ts": "import {Ev} from '../contexts/users/contracts/events'; export const S=1",
    }, None, {"ddd-context-contracts", "ddd-domain-inner", "ddd-domain-no-framework", "ddd-application-inner",
              "ddd-shared-no-contexts"},
        {"src/contexts/billing/application/h.ts -> src/contexts/users/contracts/events.ts"}),
}


@unittest.skipUnless(DEPCRUISE and os.path.isfile(DEPCRUISE), "нет DEVKIT_DEPCRUISE")
class LiveRulesTest(unittest.TestCase):
    def cruise(self, folder: str, extra: list = None) -> subprocess.CompletedProcess:
        return subprocess.run([DEPCRUISE, "src"] + (extra or []), cwd=folder, capture_output=True, text=True, timeout=120)

    def make(self, folder: str, arch: str, files: dict, variant: str = None) -> None:
        for rel, body in files.items():
            path = os.path.join(folder, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(body + "\n")
        with open(os.path.join(folder, "tsconfig.json"), "w", encoding="utf-8") as f:
            f.write(TSCONFIG)
        with open(os.path.join(folder, ".dependency-cruiser.cjs"), "w", encoding="utf-8") as f:
            f.write(arch_contract.render_depcruise(arch, variant, "src", "tsconfig.json"))

    def test_every_rule_fires_and_allowed_pass(self) -> None:
        self.assertEqual(set(CASES), set(arch_contract.ARCHS))
        for arch, (files, variant, expected, allowed) in CASES.items():
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as folder:
                self.make(folder, arch, files, variant)
                proc = self.cruise(folder, ["--output-type", "json"])
                errors = [v for v in json.loads(proc.stdout)["summary"]["violations"] if v["rule"]["severity"] == "error"]
                self.assertEqual({v["rule"]["name"] for v in errors}, expected)
                self.assertFalse(allowed & {"%s -> %s" % (v["from"], v["to"]) for v in errors})

    def test_baseline_ratchet(self) -> None:
        files, variant, _, _ = CASES["react-fsd"]
        with tempfile.TemporaryDirectory() as folder:
            self.make(folder, "react-fsd", files, variant)
            self.assertNotEqual(self.cruise(folder, ["--ignore-known"]).returncode, 0, "без baseline должно падать")
            baseline = self.cruise(folder, ["--output-type", "baseline"]).stdout
            with open(os.path.join(folder, ".dependency-cruiser-known-violations.json"), "w") as f:
                f.write(baseline)
            self.assertGreater(arch_contract.count_violations(baseline), 0)
            self.assertEqual(self.cruise(folder, ["--ignore-known"]).returncode, 0, "старые нарушения не валят")
            with open(os.path.join(folder, "src/shared/ui/bad.ts"), "w") as f:
                f.write("import {F} from '@/features/auth'; export const Z=F\n")
            self.assertNotEqual(self.cruise(folder, ["--ignore-known"]).returncode, 0, "новое нарушение валит")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 7: Прогони живой тест на настоящем depcruise**

```bash
mkdir -p "${TMPDIR:-/tmp}/devkit-depcruise" && cd "${TMPDIR:-/tmp}/devkit-depcruise" && npm init -y >/dev/null && npm i -D dependency-cruiser@18 typescript@5 >/dev/null
cd - && DEVKIT_DEPCRUISE="${TMPDIR:-/tmp}/devkit-depcruise/node_modules/.bin/depcruise" python3 -m unittest tests.test_arch_live -v
```

Expected: PASS, 2 теста. Без переменной `python3 -m unittest tests.test_arch_live -v` дает `skipped 'нет DEVKIT_DEPCRUISE'`.

- [ ] **Step 8: Полный прогон и коммит**

Run: `./tests/run.sh`
Expected: все PASS, живой тест skipped.

```bash
git add refs/arch/depcruise scripts/arch_contract.py tests/test_arch_contract.py tests/test_arch_live.py
```

Выдай человеку: `! git commit -m "feat(arch): depcruise rule templates and arch_contract script"`

---

### Task 2: ref React-архитектур и каталог

**Files:**
- Create: `refs/arch/react-fsd.md`, `refs/arch/react-feod.md`, `refs/arch/react-evolution.md`, `refs/arch/react-feature.md`, `refs/arch/react-clean.md`, `refs/arch/catalog.md`
- Modify: `tests/test_texts.py:24-26` (glob `refs/**/*.md`)
- Test: `tests/test_arch_refs.py`

**Interfaces:**
- Consumes: `arch_contract.TEMPLATES`, шаблоны из Task 1.
- Produces:
  - Ref с разделами второго уровня строго в порядке `Когда брать`, `Дерево`, `Импорты`, `Public API`, `Куда класть`, `Антипаттерны`, `Признаки`, `Источники`.
  - Блок `json` в разделе `Признаки` с ключами `requires_dep`, `dirs_all`, `dirs_any`, `dirs_none`, `files_any`, `bonus_files`, `weight`. Его читает `arch_detect.load_signatures` в Task 4.
  - `tests/test_arch_refs.py` с константами `REACT`, `NEST`, `IDS`, `SECTIONS` и функцией `section(text, name) -> str`. Task 3 расширяет `IDS`, Task 4 импортирует `section`.

- [ ] **Step 1: Напиши падающий тест**

`tests/test_arch_refs.py`:

```python
import json
import os
import re
import unittest

from tests.helpers import ROOT

ARCH = os.path.join(ROOT, "refs", "arch")
TEMPLATES = os.path.join(ARCH, "depcruise")
REACT = ["react-fsd", "react-feod", "react-evolution", "react-feature", "react-clean"]
NEST = []
IDS = REACT + NEST
SECTIONS = ["Когда брать", "Дерево", "Импорты", "Public API", "Куда класть", "Антипаттерны", "Признаки", "Источники"]
SIGNATURE_KEYS = {"requires_dep", "dirs_all", "dirs_any", "dirs_none", "files_any", "bonus_files", "weight"}


def read(name: str) -> str:
    with open(os.path.join(ARCH, name), encoding="utf-8") as f:
        return f.read()


def section(text: str, name: str) -> str:
    match = re.search(r"^## %s\n(.*?)(?=^## |\Z)" % re.escape(name), text, re.S | re.M)
    return match.group(1) if match else ""


def signature(text: str) -> dict:
    match = re.search(r"```json\n(.*?)\n```", section(text, "Признаки"), re.S)
    return json.loads(match.group(1)) if match else {}


def rule_names(arch: str) -> list:
    names = []
    for suffix in ("", ".medium"):
        path = os.path.join(TEMPLATES, arch + suffix + ".json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                names += [r["name"] for r in json.load(f)["forbidden"]]
    return names


class ArchRefsTest(unittest.TestCase):
    def test_sections_in_order(self) -> None:
        for arch in IDS:
            headings = re.findall(r"^## (.+)$", read(arch + ".md"), re.M)
            self.assertEqual(headings, SECTIONS, arch)

    def test_signature(self) -> None:
        for arch in IDS:
            sig = signature(read(arch + ".md"))
            self.assertEqual(set(sig), SIGNATURE_KEYS, arch)
            self.assertTrue(sig["requires_dep"], arch)
            self.assertTrue(sig["dirs_all"] or sig["dirs_any"] or sig["files_any"], arch)

    def test_every_rule_explained(self) -> None:
        for arch in IDS:
            text = read(arch + ".md")
            for name in rule_names(arch):
                self.assertIn("`%s`" % name, text, "%s %s" % (arch, name))

    def test_sources_are_links(self) -> None:
        for arch in IDS + ["catalog"]:
            self.assertIn("https://", section(read(arch + ".md"), "Источники") if arch != "catalog"
                          else section(read("catalog.md"), "Кто так делает"), arch)

    def test_catalog(self) -> None:
        text = read("catalog.md")
        self.assertEqual(re.findall(r"^## (.+)$", text, re.M), ["Вопросы", "Рекомендации", "Кто так делает"])
        for arch in IDS:
            self.assertIn("`%s`" % arch, section(text, "Рекомендации"), arch)
        for name in ("Климов", "Primeagen"):
            self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Запусти, убедись, что падает**

Run: `python3 -m unittest tests.test_arch_refs -v`
Expected: FAIL, `FileNotFoundError` на `react-fsd.md`.

- [ ] **Step 3: Расширь стиль-тест на `refs/arch`**

В `tests/test_texts.py` функция `texts()` сейчас:

```python
def texts() -> list:
    found = glob.glob(os.path.join(ROOT, "refs", "*.md")) + glob.glob(os.path.join(ROOT, "commands", "*.md"))
    return sorted(found + glob.glob(os.path.join(ROOT, "skills", "**", "*.md"), recursive=True))
```

Замени на:

```python
def texts() -> list:
    found = glob.glob(os.path.join(ROOT, "refs", "**", "*.md"), recursive=True)
    found += glob.glob(os.path.join(ROOT, "commands", "*.md"))
    return sorted(found + glob.glob(os.path.join(ROOT, "skills", "**", "*.md"), recursive=True))
```

- [ ] **Step 4: Напиши `refs/arch/react-fsd.md`**

````markdown
# react-fsd. Feature-Sliced Design

## Когда брать

1. Фронт-команда от 3 человек, проект живет дольше года, фич больше 10.
2. Нужна общая карта проекта и внешняя документация, по которой новичок разбирается сам.
3. Команда готова к дисциплине. Каждый новый файл требует решения о слое и слайсе.
4. Не брать для MVP и прототипа. Короткий проект не окупит слои, бери `react-feature` или `react-evolution` small.

## Дерево

```
src/
  app/              провайдеры, роутер, глобальные стили
  pages/
    cart/           ui/ model/ index.ts
  widgets/
    header/         ui/ index.ts
  features/
    add-to-cart/    ui/ model/ api/ index.ts
    auth-by-email/
  entities/
    product/        ui/ model/ api/ @x/ index.ts
    user/
  shared/
    ui/ api/ lib/ config/
```

Next.js App Router. Корневой `app/` занят роутером, код FSD живет в `src/`, слой `app` FSD это `src/app`. Файлы роутера только реэкспортируют страницы из `src/pages`. Пустой корневой `pages/` с `README.md` не дает Next включить старый роутер. Корень исходников `src`.

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `app` | все слои ниже | |
| `pages` | `widgets`, `features`, `entities`, `shared` | `fsd-layers-pages` |
| `widgets` | `features`, `entities`, `shared` | `fsd-layers-widgets` |
| `features` | `entities`, `shared` | `fsd-layers-features` |
| `entities` | `shared`, другую сущность только через `@x` | `fsd-layers-entities` |
| `shared` | только `shared` | `fsd-layers-shared` |

Слайс не импортирует соседний слайс своего слоя, правило `fsd-cross-slice`. Исключение это `entities/<x>/@x/<потребитель>.ts`. Циклы и файлы без импортеров ловят `no-circular` и `no-orphans` в `warn`. Структуру слайсов и сегментов проверяет steiger.

## Public API

1. У каждого слайса `index.ts`. Он экспортирует только то, что нужно снаружи.
2. Снаружи слайса импорт только из его `index.ts`, правило `fsd-public-api`. `@/features/auth/model/store` запрещен, `@/features/auth` можно.
3. Сущность отдает API другой сущности через `entities/<x>/@x/<потребитель>.ts`.
4. У `shared` нет общего индекса. Индекс у каждого сегмента, `@/shared/ui`, `@/shared/lib/date`.

## Куда класть

| новый код | путь |
|-----------|------|
| страница роута | `pages/<страница>/ui/` |
| крупный блок из нескольких фич, нужен нескольким страницам | `widgets/<блок>/ui/` |
| действие пользователя с бизнес-ценностью, форма, кнопка с логикой | `features/<действие>/` |
| бизнес-сущность, ее тип, стор, запросы, карточка | `entities/<сущность>/` |
| UI-кит, http-клиент, утилиты без бизнес-смысла | `shared/<сегмент>/` |
| провайдеры, роутер, глобальные стили | `app/` |
| код нужен только одной странице | внутри этой страницы, заранее не выносить |

## Антипаттерны

1. Фича импортирует фичу. Собери их в виджете или странице, общий кусок спусти в `entities` или `shared`.
2. Все подряд в `features`. Кнопка без бизнес-логики живет в `shared/ui`, просмотр сущности в `entities`.
3. Бизнес-логика в `shared`. Код знает про пользователя или заказ, значит он в `entities`.
4. Импорт в обход `index.ts`. Добавь нужный экспорт в public API слайса.
5. Слайс из 1 файла, который нужен 1 странице. Держи код в странице, пока он не понадобится второй раз.

## Признаки

```json
{
  "requires_dep": ["react", "next"],
  "dirs_all": ["shared"],
  "dirs_any": ["entities", "widgets"],
  "dirs_none": ["services", "modules", "domain"],
  "files_any": [],
  "bonus_files": ["steiger.config.*"],
  "weight": 1.0
}
```

## Источники

1. https://feature-sliced.design/docs/get-started/overview
2. https://feature-sliced.design/docs/guides/tech/with-nextjs
3. https://github.com/feature-sliced/steiger
````

- [ ] **Step 5: Напиши `refs/arch/react-feod.md`**

````markdown
# react-feod. Fractal Entity Oriented Design

## Когда брать

1. Несколько команд или микрофронтенды, нужна одна карта на все приложения.
2. Границы модулей нужны, а терминология FSD (entity, feature, widget) команде мешает.
3. Модули крупные и растут вглубь, подмодули повторяют структуру родителя.
4. Не брать для маленького проекта, там хватит `react-feature`.

## Дерево

```
src/
  app/              инициализация, роутер, провайдеры
  pages/
    catalog/        страница собирается из модулей
  modules/
    cart/
      index.ts      public API
      ui/ model/ api/
      modules/
        promo/      подмодуль с той же структурой
    user/
  common/           утилиты и UI без бизнес-логики
  global/           шимы и глобальные типы, доступны без импорта
```

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `app` | все | |
| `pages` | `modules`, `common` | `feod-pages-up` |
| `modules` | другие `modules` через их `index.ts`, `common` | `feod-modules-up` |
| `common` | только `common` | `feod-common-isolated` |
| `global` | его никто не импортирует | `feod-no-global-import` |

Модуль импортирует свои подмодули напрямую, чужой модуль только через `index.ts`, правило `feod-public-api`. Подмодули внутри модуля подчиняются тем же правилам, это проверяет ревью, линтер видит верхний уровень.

## Public API

1. У каждого модуля и подмодуля `index.ts`. Наружу только он.
2. Импорт `@/modules/cart/model/store` снаружи `cart` запрещен, `@/modules/cart` можно.
3. Подмодуль виден снаружи только через `index.ts` родителя.

## Куда класть

| новый код | путь |
|-----------|------|
| страница роута | `pages/<страница>/` |
| бизнес-функциональность | `modules/<модуль>/` |
| часть модуля со своей логикой | `modules/<модуль>/modules/<подмодуль>/` |
| утилита, UI-кит без бизнес-смысла | `common/` |
| полифил, глобальный тип | `global/` |
| провайдеры, роутер | `app/` |

## Антипаттерны

1. `common` знает про бизнес. Перенеси код в модуль, который им владеет.
2. Модуль на каждую сущность бэкенда. Модуль это кусок функциональности, а не таблица.
3. Импорт в обход `index.ts`. Добавь экспорт в public API модуля.
4. Импорт из `app`. Передай зависимость параметром или через контекст.

## Признаки

```json
{
  "requires_dep": ["react", "next"],
  "dirs_all": ["modules"],
  "dirs_any": ["common", "global"],
  "dirs_none": ["features", "entities", "widgets"],
  "files_any": [],
  "bonus_files": [],
  "weight": 1.0
}
```

## Источники

1. https://feod.dev
2. https://habr.com/ru/companies/sportmaster_lab/articles/972410/
3. https://fractal-oriented.tech
````

- [ ] **Step 6: Напиши `refs/arch/react-evolution.md`**

````markdown
# react-evolution. Evolution Design

## Когда брать

1. Нужен порядок FSD без его сетки из 6 слоев.
2. Вариант small для проекта до 12 человеко-месяцев, medium для команды до 5 или 6 фронтов.
3. Фичи крупные. 3 или 4 фичи на старте это норма.
4. Не брать для библиотек.

## Дерево

```
src/
  app/              запуск, роутер, композиция фич в страницы
  features/
    auth/           index.ts ui/ model/ api/
    task-list/
  services/         в medium, переиспользуемые бизнес-модули
    session/
  shared/           ui/ lib/ api/, может содержать бизнес-логику
```

Вариант записан в `variant` во frontmatter `ARCHITECTURE.md`. small разрешает импорт фичи из фичи, medium запрещает.

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `app` | все | |
| `features` | `services`, `shared`, в small другие фичи | `ed-no-app`, в medium `ed-cross-feature` |
| `services` | другие `services`, `shared` | `ed-no-features` |
| `shared` | только `shared` | `ed-shared-no-services` |

В medium фичи связываются через `app`, общий стейт в `services`, слоты, render props, события, контекст или DI.

## Public API

1. У каждой фичи и сервиса `index.ts`, правило `ed-public-api`.
2. Внутренности модуля это группы `ui`, `model`, `api`, снаружи их не импортируют.
3. У `shared` нет общего индекса, импорт по сегментам.

## Куда класть

| новый код | путь |
|-----------|------|
| крупный кусок функциональности вместе с его страницей | `features/<фича>/` |
| страница из нескольких фич | `app/` |
| логика и UI, нужные нескольким фичам | `services/<сервис>/` в medium, `shared/` в small |
| UI-кит, утилиты, http-клиент | `shared/` |
| роутер, провайдеры, глобальные стили | `app/` |

## Антипаттерны

1. Мелкие фичи. Фича на кнопку размывает границы, объедини с соседями.
2. Импорт из `app`. Там самый часто меняющийся код, зависимость на него ломает фичи.
3. В medium фича импортирует фичу. Перенеси общее в `services` или свяжи через `app`.
4. `services` зависит от `features`. Сервис переиспользуют несколько фич, он должен быть стабильнее их.

## Признаки

```json
{
  "requires_dep": ["react", "next"],
  "dirs_all": ["features", "shared"],
  "dirs_any": ["services", "app"],
  "dirs_none": ["entities", "widgets", "modules", "components", "pages"],
  "files_any": [],
  "bonus_files": ["evo.config.*"],
  "weight": 1.0
}
```

## Источники

1. https://github.com/ep-community/evolution-design
2. https://frontendconf.ru/moscow/2025/abstracts/15667
````

- [ ] **Step 7: Напиши `refs/arch/react-feature.md`**

````markdown
# react-feature. Раскладка по фичам, Bulletproof React

## Когда брать

1. MVP, прототип, 1 или 2 человека.
2. Фич немного, домен простой.
3. Нужна раскладка, которую понимает любой React-разработчик без обучения.
4. Перерастает, когда фичам нужен общий бизнес-код. Путь роста в `react-evolution`.

## Дерево

```
src/
  app/              роуты, провайдеры, композиция фич
    routes/
  features/
    discussions/    api/ components/ hooks/ stores/ types/ utils/
    comments/
  components/       общий UI без бизнес-логики
  hooks/
  lib/              настроенные библиотеки, http-клиент
  utils/
  types/ config/ stores/ api/ assets/ testing/
```

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `app` | `features` и общий код | |
| `features` | общий код, свою фичу | `feature-cross`, `feature-no-app` |
| общий код `components`, `hooks`, `lib`, `utils`, `types`, `config`, `stores`, `api` | только общий код | `feature-shared-up` |

## Public API

Bulletproof React не требует `index.ts` у фичи и советует прямые импорты ради tree shaking. Отдельного правила public API нет. Граница это запрет импорта фичи из фичи.

## Куда класть

| новый код | путь |
|-----------|------|
| экран или роут | `app/routes/` |
| функциональность со своими запросами и состоянием | `features/<фича>/` |
| UI без бизнес-логики, нужен 2 фичам | `components/` |
| хук без бизнес-логики | `hooks/` |
| настроенный axios, query client | `lib/` |
| код нужен 2 фичам и знает бизнес | композиция в `app/` или переход в `react-evolution`, где `shared` держит бизнес-логику |

## Антипаттерны

1. Фича импортирует фичу. Собери их в `app`.
2. Общий код знает про фичу. Перенеси его в фичу.
3. `components` как свалка бизнес-компонентов. Компонент с запросами и стором живет в фиче.

## Признаки

```json
{
  "requires_dep": ["react", "next"],
  "dirs_all": ["features"],
  "dirs_any": ["components", "hooks", "lib", "utils"],
  "dirs_none": ["entities", "widgets", "shared", "modules", "domain", "services"],
  "files_any": [],
  "bonus_files": [],
  "weight": 1.0
}
```

## Источники

1. https://github.com/alan2207/bulletproof-react/blob/master/docs/project-structure.md
````

- [ ] **Step 8: Напиши `refs/arch/react-clean.md`**

````markdown
# react-clean. Clean и Hexagonal на фронте

## Когда брать

1. Сложная логика на клиенте, редакторы, расчеты, офлайн. Ее нужно тестировать без React.
2. Источник данных меняется, REST на GraphQL, бэкенд на мок.
3. Команда знает порты и адаптеры.
4. Не брать для CRUD поверх API. Слои станут пустыми прокладками.

## Дерево

```
src/
  domain/           сущности и правила, чистый TS
    cart.ts
  application/      сценарии и порты
    add-to-cart.ts
    ports.ts
  infrastructure/   адаптеры портов, http, storage
    cart-api.ts
  ui/               React компоненты и хуки, сборка зависимостей
    cart/
```

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `ui` или `presentation` | `application`, `domain`, `infrastructure` для сборки зависимостей | |
| `infrastructure` | `application`, `domain` | `clean-infrastructure-no-ui` |
| `application` | `domain` | `clean-application-inner` |
| `domain` | ничего из проекта, без React и HTTP-клиентов | `clean-domain-inner`, `clean-domain-no-libs` |

## Public API

1. Сценарий `application` это 1 файл с 1 экспортом.
2. `ui` зовет сценарии. В `infrastructure` он ходит только в точке сборки зависимостей.
3. Порты это интерфейсы в `application/ports.ts`, адаптеры их реализуют.

## Куда класть

| новый код | путь |
|-----------|------|
| бизнес-правило, расчет, тип сущности | `domain/` |
| сценарий пользователя | `application/<сценарий>.ts` |
| интерфейс внешнего мира | `application/ports.ts` |
| http, localStorage, SDK | `infrastructure/` |
| компонент, хук, страница | `ui/` |
| создание адаптеров и передача в сценарии | `ui/`, точка сборки, например провайдер |

## Антипаттерны

1. `domain` импортирует React или axios. Вынеси вызов в адаптер, в домене оставь данные и правила.
2. Сценарий зовет `fetch`. Объяви порт и передай адаптер.
3. Компонент ходит в http мимо сценария. Логика расползается по UI.
4. Слои ради слоев. Сценарий, который только пробрасывает вызов, удали.

## Признаки

```json
{
  "requires_dep": ["react", "next"],
  "dirs_all": ["domain"],
  "dirs_any": ["application", "infrastructure"],
  "dirs_none": ["entities", "widgets", "modules"],
  "files_any": [],
  "bonus_files": [],
  "weight": 1.0
}
```

## Источники

1. https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
2. https://alistair.cockburn.us/hexagonal-architecture/
````

- [ ] **Step 9: Напиши `refs/arch/catalog.md`**

````markdown
# Каталог архитектур

Выбор на старте и путь роста. Правила каждой архитектуры в `<id>.md` рядом.

## Вопросы

1. Сколько человек будет писать этот пакет через год. 1 или 2, от 3 до 6, больше 6 или несколько команд.
2. Насколько сложен домен. CRUD и формы, есть правила и состояния, много правил, инвариантов и процессов.
3. Сколько проект проживет. Прототип или MVP, от полугода до 2 лет, дольше.
4. Где живет бизнес-логика. В основном на сервере, или заметная часть на клиенте, офлайн, расчеты, редакторы.
5. Это пакет монорепо, где соседние пакеты уже выбрали архитектуру. Да, бери ту же для того же стека, если нет причины иначе.

## Рекомендации

### React

| ответы | рекомендация | альтернатива |
|--------|--------------|--------------|
| 1 или 2 человека, прототип или MVP | `react-feature` | `react-evolution` small |
| 1 или 2 человека, проект надолго | `react-evolution` small | `react-feature` |
| от 3 до 6, CRUD или средний домен | `react-evolution` medium | `react-fsd` |
| от 3 до 6, нужен стандарт с внешней документацией | `react-fsd` | `react-evolution` medium |
| больше 6 или несколько команд, микрофронтенды | `react-feod` | `react-fsd` |
| сложная логика на клиенте, тесты без UI | `react-clean` | `react-evolution` medium |

Путь роста. `react-feature` переходит в `react-evolution` small почти без переноса, `components`, `hooks`, `lib` уезжают в `shared`. small переходит в medium, когда фичи начинают мешать друг другу. Переход в FSD это перенос кода по слоям, его планируют отдельно.

### NestJS

| ответы | рекомендация | альтернатива |
|--------|--------------|--------------|
| CRUD, любая команда | `nest-standard` | |
| в сервисах копятся правила, их хочется тестировать без Nest и ORM | `nest-modular-clean` | `nest-standard` |
| сложный домен, несколько команд, события между частями системы | `nest-ddd-cqrs` | `nest-modular-clean` |

Путь роста. `nest-standard` переходит в `nest-modular-clean` без смены границ модулей, модуль переезжает в `modules/<x>` и делится на слои. `nest-ddd-cqrs` берут, когда модули стали bounded contexts со своим языком.

## Кто так делает

Решение по таблице выше. Ниже происхождение вариантов.

1. FSD. Стандарт с документацией и линтером steiger. https://feature-sliced.design
2. Евгений Паромов вел курс по FSD, на Merge 2024 разобрал 3 главных недостатка FSD, затем с сообществом сделал Evolution Design. https://skolkovo2024.mergeconf.ru/speakers/development/frontend/paromov и https://github.com/ep-community/evolution-design
3. FEOD от Спортмастер Lab, упрощенный FSD с фрактальными модулями. https://habr.com/ru/companies/sportmaster_lab/articles/972410/
4. Bulletproof React, самый известный шаблон раскладки по фичам. https://github.com/alan2207/bulletproof-react
5. Matt Pocock. Глубокие модули и маленькие интерфейсы это ось дизайна внутри любой архитектуры, см. `refs/codebase-design.md`. https://github.com/mattpocock/skills
6. Структуру не усложняют раньше, чем ее окупит размер проекта. Поэтому для MVP таблица дает `react-feature` и `nest-standard`.
7. NestJS. Модули по фичам из документации https://docs.nestjs.com/modules, CQRS из https://docs.nestjs.com/recipes/cqrs
````

Таблица `Рекомендации` должна упоминать все 8 id. После Task 3 тест это проверит, nest-id уже есть в таблице.

- [ ] **Step 10: Запусти тесты**

Run: `python3 -m unittest tests.test_arch_refs tests.test_texts -v`
Expected: PASS. Упал стиль-тест на `refs/arch/...`, перепиши фразу. Упал `test_every_rule_explained`, упомяни правило в разделе `Импорты` в обратных кавычках.

- [ ] **Step 11: Коммит**

```bash
git add refs/arch/react-*.md refs/arch/catalog.md tests/test_arch_refs.py tests/test_texts.py
```

Выдай человеку: `! git commit -m "docs(arch): react architecture refs and selection catalog"`

---

### Task 3: ref NestJS-архитектур

**Files:**
- Create: `refs/arch/nest-standard.md`, `refs/arch/nest-modular-clean.md`, `refs/arch/nest-ddd-cqrs.md`
- Modify: `tests/test_arch_refs.py` (константа `NEST`, тест полноты)

**Interfaces:**
- Consumes: `tests/test_arch_refs.py` из Task 2, шаблоны из Task 1.
- Produces: `NEST = ["nest-standard", "nest-modular-clean", "nest-ddd-cqrs"]`, `IDS` из 8 id.

- [ ] **Step 1: Сделай тест падающим**

В `tests/test_arch_refs.py` замени `NEST = []` на:

```python
NEST = ["nest-standard", "nest-modular-clean", "nest-ddd-cqrs"]
```

И добавь в класс `ArchRefsTest`:

```python
    def test_refs_match_templates(self) -> None:
        templates = {name[:-5] for name in os.listdir(TEMPLATES)
                     if name.endswith(".json") and name != "base.json" and name.count(".") == 1}
        self.assertEqual(templates, set(IDS))
        refs = {name[:-3] for name in os.listdir(ARCH) if name.endswith(".md") and name != "catalog.md"}
        self.assertEqual(refs, set(IDS))
```

- [ ] **Step 2: Запусти, убедись, что падает**

Run: `python3 -m unittest tests.test_arch_refs -v`
Expected: FAIL, `FileNotFoundError` на `nest-standard.md`.

- [ ] **Step 3: Напиши `refs/arch/nest-standard.md`**

````markdown
# nest-standard. Модули по фичам из документации Nest

## Когда брать

1. CRUD и средняя логика.
2. Новый проект на Nest, раскладка из `nest new` и документации.
3. Команда знает Nest, обучение не нужно.
4. Перерастает, когда сервисы толстеют от правил. Путь роста в `nest-modular-clean`.

## Дерево

```
src/
  main.ts
  app.module.ts
  users/
    users.module.ts
    users.controller.ts
    users.service.ts
    users.repository.ts     если нужен слой над ORM
    dto/
      create-user.dto.ts
    entities/
      user.entity.ts
  orders/
  common/                   guards, interceptors, filters, pipes, decorators
  config/
```

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `*.controller.ts`, `*.resolver.ts` | свой сервис и `dto` | `nest-controller-no-orm`, `nest-controller-no-repository` |
| `*.service.ts` | свои `repository` и `entities`, ORM, чужие `*.module.ts`, `*.service.ts`, `dto` | `nest-foreign-internals` |
| `common`, `config`, `shared` | только `common`, `config`, `shared` | `nest-common-no-features` |

## Public API

1. Модуль отдает наружу провайдеры из `exports` своего `*.module.ts`.
2. Другой модуль добавляет его в `imports` и инжектит сервис.
3. Controller, `entities` и repository чужого модуля не импортируются. DTO чужого модуля можно, это контракт.

## Куда класть

| новый код | путь |
|-----------|------|
| REST endpoint | `<модуль>/<модуль>.controller.ts` |
| GraphQL резолвер | `<модуль>/<модуль>.resolver.ts` |
| бизнес-правило | `<модуль>/<модуль>.service.ts` |
| запросы к базе | сервис или `<модуль>/<модуль>.repository.ts` |
| входные данные с `class-validator` | `<модуль>/dto/` |
| модель базы | `<модуль>/entities/` или `schema.prisma` |
| guard, pipe, filter, interceptor | `common/` |
| конфиг | `config/` через `ConfigModule` |

## Антипаттерны

1. Контроллер зовет Prisma или репозиторий. Вызов идет через сервис.
2. Сервис на 1000 строк с правилами. Это сигнал перейти в `nest-modular-clean`.
3. Циклы модулей и `forwardRef` без причины. Общее вынеси в отдельный модуль.
4. Импорт `entities` чужого модуля. Попроси данные у его сервиса.

## Признаки

```json
{
  "requires_dep": ["@nestjs/core"],
  "dirs_all": [],
  "dirs_any": [],
  "dirs_none": ["modules", "contexts", "*/domain", "*/infrastructure"],
  "files_any": ["app.module.ts", "*/*.module.ts"],
  "bonus_files": [],
  "weight": 1.0
}
```

## Источники

1. https://docs.nestjs.com/modules
2. https://docs.nestjs.com/cli/usages
````

- [ ] **Step 4: Напиши `refs/arch/nest-modular-clean.md`**

````markdown
# nest-modular-clean. Модульный монолит с чистыми слоями

## Когда брать

1. В сервисах копятся правила, их хочется тестировать без Nest и базы.
2. Модули крупные, у каждого свои сценарии и хранилище.
3. ORM или внешний клиент могут смениться.
4. Не брать для CRUD. Слои станут прокладками, хватит `nest-standard`.

## Дерево

```
src/
  main.ts
  app.module.ts
  modules/
    users/
      index.ts              public API, модуль и экспортируемые типы
      users.module.ts
      presentation/         controllers, resolvers, dto
      application/          сервисы сценариев, порты
      domain/               сущности и правила без Nest и ORM
      infrastructure/       репозитории на ORM, внешние клиенты
    billing/
  shared/                   prisma, config, guards без бизнес-логики
```

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `presentation` | `application`, `domain` | `nmc-presentation-no-infrastructure` |
| `application` | `domain` | `nmc-application-inner` |
| `domain` | ничего из модуля, без `@nestjs/*` и ORM | `nmc-domain-inner`, `nmc-domain-no-framework` |
| `infrastructure` | `application`, `domain`, ORM | `nmc-orm-in-infrastructure` |
| другой модуль | только его `index.ts` | `nmc-public-api` |
| `shared` | без `modules` | `nmc-shared-no-modules` |

ORM разрешен в `infrastructure` модулей и в `shared`, `database`, `prisma` в корне, там живет `PrismaService`. `*.module.ts` связывает порты с адаптерами и может импортировать любой слой своего модуля.

## Public API

1. `modules/<x>/index.ts` экспортирует Nest-модуль и типы, нужные другим модулям.
2. Сервис чужого модуля доступен через `exports` его модуля и DI.
3. Порты объявлены в `application`, реализации в `infrastructure`, связь через токен провайдера в `*.module.ts`.

## Куда класть

| новый код | путь |
|-----------|------|
| endpoint, резолвер, DTO | `modules/<x>/presentation/` |
| сценарий | `modules/<x>/application/<сценарий>.service.ts` |
| порт репозитория или клиента | `modules/<x>/application/ports/` |
| правило, сущность, value object | `modules/<x>/domain/` |
| репозиторий на Prisma или TypeORM | `modules/<x>/infrastructure/` |
| `PrismaService`, конфиг, общие guards | `shared/` |

## Антипаттерны

1. `@Injectable` или Prisma в `domain`. Домен это классы и функции без фреймворка.
2. `application` импортирует `PrismaClient`. Объяви порт, реализуй в `infrastructure`.
3. Импорт `modules/billing/domain/...` из `users`. Только через `index.ts` и DI.
4. Бизнес-логика в `shared`. Перенеси в модуль, который ею владеет.

## Признаки

```json
{
  "requires_dep": ["@nestjs/core"],
  "dirs_all": ["modules"],
  "dirs_any": ["modules/*/domain", "modules/*/application", "modules/*/infrastructure"],
  "dirs_none": ["contexts"],
  "files_any": [],
  "bonus_files": [],
  "weight": 1.0
}
```

## Источники

1. https://docs.nestjs.com/modules
2. https://docs.nestjs.com/fundamentals/custom-providers
3. https://alistair.cockburn.us/hexagonal-architecture/
````

- [ ] **Step 5: Напиши `refs/arch/nest-ddd-cqrs.md`**

````markdown
# nest-ddd-cqrs. Bounded contexts и CQRS

## Когда брать

1. Сложный домен с инвариантами и процессами.
2. Несколько команд, у каждой свой контекст.
3. Части системы общаются событиями.
4. Не брать для CRUD. Команды и handlers удвоят код без пользы.

## Дерево

```
src/
  main.ts
  app.module.ts
  contexts/
    billing/
      billing.module.ts
      contracts/            события, DTO и интерфейсы для других контекстов
        invoice-paid.event.ts
      domain/               агрегаты, value objects, доменные события
        invoice.aggregate.ts
      application/
        commands/           команда и ее handler
        queries/
        event-handlers/
        ports/
      infrastructure/       репозитории, мапперы, внешние клиенты
      presentation/         controllers, resolvers
    users/
  shared/                   CqrsModule, prisma, общие типы
```

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `presentation` | `application` через `CommandBus` и `QueryBus`, `contracts` | |
| `application` | `domain`, `contracts`, свои `ports` | `ddd-application-inner` |
| `domain` | ничего из контекста, без `@nestjs/*` и ORM | `ddd-domain-inner`, `ddd-domain-no-framework` |
| `infrastructure` | `application`, `domain`, ORM | |
| другой контекст | только его `contracts` | `ddd-context-contracts` |
| `shared` | без `contexts` | `ddd-shared-no-contexts` |

## Public API

1. Наружу контекст отдает только `contracts`. События, классы запросов, DTO, интерфейсы.
2. Контексты не импортируют модули друг друга. Связь через `EventBus` и `QueryBus` с классами из `contracts`.
3. `app.module.ts` собирает модули контекстов.

## Куда класть

| новый код | путь |
|-----------|------|
| изменение состояния | `application/commands/<команда>.command.ts` и `.handler.ts` |
| чтение | `application/queries/` |
| реакция на событие другого контекста | `application/event-handlers/` |
| инвариант, правило | метод агрегата в `domain/` |
| событие для других контекстов | `contracts/` |
| репозиторий, маппер | `infrastructure/` |

## Антипаттерны

1. Бизнес-правило в handler. Handler грузит агрегат, зовет метод, сохраняет.
2. Агрегат меняют сеттерами снаружи. Состояние меняется только методами агрегата, это проверяет ревью.
3. Импорт `domain` чужого контекста. Нужные данные отдает событие или запрос из `contracts`.
4. CQRS для CRUD. Простое чтение и запись остаются в `nest-standard`.

## Признаки

```json
{
  "requires_dep": ["@nestjs/cqrs"],
  "dirs_all": ["contexts"],
  "dirs_any": ["contexts/*/domain", "contexts/*/application", "contexts/*/contracts"],
  "dirs_none": [],
  "files_any": [],
  "bonus_files": [],
  "weight": 1.0
}
```

## Источники

1. https://docs.nestjs.com/recipes/cqrs
2. https://martinfowler.com/bliki/BoundedContext.html
````

- [ ] **Step 6: Запусти тесты**

Run: `python3 -m unittest tests.test_arch_refs tests.test_texts -v`
Expected: PASS.

- [ ] **Step 7: Коммит**

```bash
git add refs/arch/nest-*.md tests/test_arch_refs.py
```

Выдай человеку: `! git commit -m "docs(arch): nestjs architecture refs"`

---

### Task 4: `arch_detect.py`

**Files:**
- Create: `scripts/arch_detect.py`
- Test: `tests/test_arch_detect.py`

**Interfaces:**
- Consumes: блоки `Признаки` из `refs/arch/<id>.md` (Task 2 и 3), `tests.test_arch_refs.section`, `tests.test_arch_refs.IDS`.
- Produces:
  - `arch_detect.REFS: str`, `LAYERS: Dict[str, List[List[str]]]`, `PICK_SCORE = 0.6`, `PICK_GAP = 0.15`.
  - `load_signatures(refs_dir: str = REFS) -> Dict[str, Dict[str, Any]]`.
  - `find_roots(path: str) -> List[str]`, абсолютные пути пакетов с React или Nest.
  - `analyze(package_dir: str, sigs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]`, корень с ключами `root`, `stack`, `src`, `pick`, `candidates`.
  - `pick(candidates: List[Dict[str, Any]]) -> Optional[str]`.
  - CLI `python3 scripts/arch_detect.py [путь]` печатает `{"roots": [...]}`, `root` относительно пути.

- [ ] **Step 1: Напиши падающий тест**

`tests/test_arch_detect.py`:

```python
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import SCRIPTS
from tests.test_arch_refs import ARCH, IDS, section

sys.path.insert(0, SCRIPTS)
import arch_detect  # noqa: E402

REACT = {"dependencies": {"react": "^19.0.0"}}
NEST = {"dependencies": {"@nestjs/core": "^11.0.0"}}
NEST_CQRS = {"dependencies": {"@nestjs/core": "^11.0.0", "@nestjs/cqrs": "^11.0.0"}}


class DetectCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self._tmp.name)
        self.sigs = arch_detect.load_signatures()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, rel: str, body: str = "export {}\n") -> None:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)

    def package(self, rel: str, pkg: dict) -> None:
        self.write(os.path.join(rel, "package.json"), json.dumps(pkg))

    def tree(self, rel: str, files: dict) -> None:
        for name, body in files.items():
            self.write(os.path.join(rel, name), body)

    def result(self, rel: str = "") -> dict:
        return arch_detect.analyze(os.path.join(self.root, rel), self.sigs)


FSD = {
    "src/app/index.tsx": "import {P} from '../pages/home'\n",
    "src/pages/home/index.ts": "import {W} from '../../widgets/header'\n",
    "src/widgets/header/index.ts": "import {F} from '../../features/auth'\n",
    "src/features/auth/index.ts": "import {U} from '../../entities/user'\n",
    "src/entities/user/index.ts": "import {B} from '../../shared/ui'\n",
    "src/shared/ui/index.ts": "export const B = 1\n",
}


class SignaturesTest(DetectCase):
    def test_all_refs_have_signatures(self) -> None:
        self.assertEqual(set(self.sigs), set(IDS))
        self.assertEqual(set(arch_detect.LAYERS), set(IDS))

    def test_layers_named_in_refs(self) -> None:
        for arch, tiers in arch_detect.LAYERS.items():
            with open(os.path.join(ARCH, arch + ".md"), encoding="utf-8") as f:
                imports = section(f.read(), "Импорты")
            for layer in (name for tier in tiers for name in tier):
                self.assertIn("`%s`" % layer, imports, "%s %s" % (arch, layer))


class PickTest(DetectCase):
    def check(self, files: dict, pkg: dict, expected: str) -> dict:
        self.package("", pkg)
        self.tree("", files)
        found = self.result()
        self.assertEqual(found["pick"], expected, json.dumps(found["candidates"][:3], ensure_ascii=False))
        return found

    def test_fsd(self) -> None:
        found = self.check(FSD, REACT, "react-fsd")
        self.assertEqual(found["stack"], "react")
        self.assertEqual(found["src"], "src")

    def test_feod(self) -> None:
        self.check({"src/app/index.tsx": "", "src/pages/home/index.ts": "", "src/modules/cart/index.ts": "",
                    "src/common/x.ts": ""}, REACT, "react-feod")

    def test_evolution_medium(self) -> None:
        self.check({"src/app/index.tsx": "", "src/features/tasks/index.ts": "", "src/services/session/index.ts": "",
                    "src/shared/lib/index.ts": ""}, REACT, "react-evolution")

    def test_evolution_small(self) -> None:
        self.check({"src/app/index.tsx": "import {T} from '../features/tasks'\n", "src/features/tasks/index.ts": "",
                    "src/shared/lib/index.ts": ""}, REACT, "react-evolution")

    def test_feature(self) -> None:
        self.check({"src/app/index.tsx": "", "src/features/tasks/components/list.tsx": "",
                    "src/components/button.tsx": "", "src/hooks/use-x.ts": "", "src/lib/api.ts": ""},
                   REACT, "react-feature")

    def test_clean(self) -> None:
        self.check({"src/domain/cart.ts": "", "src/application/add.ts": "import {C} from '../domain/cart'\n",
                    "src/infrastructure/api.ts": "", "src/ui/page.tsx": ""}, REACT, "react-clean")

    def test_nest_new_is_standard(self) -> None:
        found = self.check({"src/main.ts": "", "src/app.module.ts": "", "src/app.controller.ts": "",
                            "src/app.service.ts": ""}, NEST, "nest-standard")
        self.assertEqual(found["stack"], "nest")

    def test_nest_standard_with_modules(self) -> None:
        self.check({"src/app.module.ts": "", "src/users/users.module.ts": "", "src/users/dto/x.dto.ts": "",
                    "src/orders/orders.module.ts": ""}, NEST, "nest-standard")

    def test_nest_modular_clean(self) -> None:
        self.check({"src/app.module.ts": "", "src/modules/users/index.ts": "",
                    "src/modules/users/domain/user.ts": "", "src/modules/users/application/x.service.ts": "",
                    "src/modules/users/infrastructure/repo.ts": ""}, NEST, "nest-modular-clean")

    def test_nest_ddd(self) -> None:
        self.check({"src/app.module.ts": "", "src/contexts/billing/domain/invoice.ts": "",
                    "src/contexts/billing/application/commands/pay.handler.ts": "",
                    "src/contexts/billing/contracts/paid.event.ts": ""}, NEST_CQRS, "nest-ddd-cqrs")


class EdgeTest(DetectCase):
    def test_mixed_has_no_pick_and_explains(self) -> None:
        self.package("", REACT)
        self.tree("", {"src/modules/a/index.ts": "", "src/common/x.ts": "", "src/features/b/index.ts": "",
                       "src/entities/c/index.ts": "", "src/shared/ui/index.ts": ""})
        found = self.result()
        self.assertIsNone(found["pick"])
        fsd = next(c for c in found["candidates"] if c["arch"] == "react-fsd")
        self.assertTrue(any("modules" in item for item in fsd["conflicts"]), fsd)

    def test_empty_react_has_no_pick(self) -> None:
        self.package("", REACT)
        found = self.result()
        self.assertIsNone(found["pick"])
        self.assertEqual(found["src"], ".")

    def test_without_src_uses_package_root(self) -> None:
        self.package("", REACT)
        self.tree("", {name[len("src/"):]: body for name, body in FSD.items()})
        found = self.result()
        self.assertEqual(found["src"], ".")
        self.assertEqual(found["pick"], "react-fsd")

    def test_next_router_app_ignored(self) -> None:
        self.package("", {"dependencies": {"next": "15.0.0", "react": "19.0.0"}})
        self.tree("", dict(FSD, **{"app/page.tsx": "export {}\n", "app/layout.tsx": "export {}\n"}))
        self.assertEqual(self.result()["pick"], "react-fsd")

    def test_only_candidates_of_own_stack(self) -> None:
        self.package("", NEST)
        self.write("src/app.module.ts")
        self.assertTrue(all(c["arch"].startswith("nest-") for c in self.result()["candidates"]))

    def test_bonus_file(self) -> None:
        self.package("", REACT)
        self.tree("", {"src/shared/ui/index.ts": "", "src/features/a/index.ts": "", "steiger.config.ts": ""})
        fsd = next(c for c in self.result()["candidates"] if c["arch"] == "react-fsd")
        self.assertTrue(any("steiger.config.ts" in item for item in fsd["evidence"]), fsd)

    def test_imports_against_layers_lower_score(self) -> None:
        self.package("good", REACT)
        self.tree("good", FSD)
        self.package("bad", REACT)
        self.tree("bad", dict(FSD, **{
            "src/shared/ui/index.ts": "import {F} from '../../features/auth'\nimport {W} from '../../widgets/header'\n",
            "src/entities/user/index.ts": "import {P} from '../../pages/home'\n"}))
        score = lambda rel: next(c["score"] for c in self.result(rel)["candidates"] if c["arch"] == "react-fsd")
        self.assertGreater(score("good"), score("bad"))

    def test_tsconfig_with_comments_and_alias(self) -> None:
        self.package("", REACT)
        self.tree("", {
            "tsconfig.json": '{\n  // Vite\n  "compilerOptions": {\n    /* alias */\n    "baseUrl": ".",\n'
                             '    "paths": {"@/*": ["src/*"],},\n  },\n}\n',
            "src/shared/ui/index.ts": "import {F} from '@/features/auth'\n",
            "src/features/auth/index.ts": "", "src/entities/user/index.ts": "",
        })
        fsd = next(c for c in self.result()["candidates"] if c["arch"] == "react-fsd")
        self.assertTrue(any("0%" in item for item in fsd["evidence"]), fsd)


class RootsTest(DetectCase):
    def test_npm_workspaces(self) -> None:
        self.package("", {"workspaces": ["apps/*"]})
        self.package("apps/web", REACT)
        self.tree("apps/web", FSD)
        self.package("apps/api", NEST)
        self.write("apps/api/src/app.module.ts")
        self.package("apps/docs", {"dependencies": {"vitepress": "1"}})
        roots = [os.path.relpath(r, self.root) for r in arch_detect.find_roots(self.root)]
        self.assertEqual(roots, ["apps/api", "apps/web"])

    def test_pnpm_workspace_with_quotes_and_negation(self) -> None:
        self.package("", {"name": "mono"})
        self.write("pnpm-workspace.yaml", "packages:\n  - 'apps/*'\n  - \"libs/*\"\n  - '!**/test/**'\n")
        self.package("apps/web", REACT)
        self.package("libs/api", NEST)
        roots = [os.path.relpath(r, self.root) for r in arch_detect.find_roots(self.root)]
        self.assertEqual(roots, ["apps/web", "libs/api"])

    def test_turbo_without_workspaces(self) -> None:
        self.package("", {"name": "mono"})
        self.write("turbo.json", "{}")
        self.package("apps/web", REACT)
        self.package("packages/ui", {"dependencies": {"react": "19"}})
        roots = [os.path.relpath(r, self.root) for r in arch_detect.find_roots(self.root)]
        self.assertEqual(roots, ["apps/web", "packages/ui"])

    def test_single_package(self) -> None:
        self.package("", REACT)
        self.assertEqual(arch_detect.find_roots(self.root), [self.root])

    def test_no_react_or_nest(self) -> None:
        self.package("", {"dependencies": {"express": "5"}})
        self.assertEqual(arch_detect.find_roots(self.root), [])

    def test_cli(self) -> None:
        self.package("", REACT)
        self.tree("", FSD)
        proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "arch_detect.py"), self.root],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["roots"][0]["root"], ".")
        self.assertEqual(data["roots"][0]["pick"], "react-fsd")


class PickRuleTest(unittest.TestCase):
    def test_threshold_and_gap(self) -> None:
        cand = lambda *scores: [{"arch": "a%d" % i, "score": s} for i, s in enumerate(scores)]
        self.assertEqual(arch_detect.pick(cand(0.6)), "a0")
        self.assertIsNone(arch_detect.pick(cand(0.59)))
        self.assertEqual(arch_detect.pick(cand(0.8, 0.65)), "a0")
        self.assertIsNone(arch_detect.pick(cand(0.8, 0.66)))
        self.assertIsNone(arch_detect.pick([]))


if __name__ == "__main__":
    unittest.main()
```

Пояснения к ожиданиям. В `test_tsconfig_with_comments_and_alias` единственный импорт между слоями идет вверх из `shared` в `features` через `@/`. Если алиас разобран, evidence содержит `по правилам 0%`. В `test_turbo_without_workspaces` globs `apps/*`, `packages/*`, `libs/*`. В `test_nest_new_is_standard` у `nest-modular-clean` нет `modules`, у `nest-ddd-cqrs` нет `@nestjs/cqrs`, оба дают 0.

- [ ] **Step 2: Запусти, убедись, что падает**

Run: `python3 -m unittest tests.test_arch_detect -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'arch_detect'`.

- [ ] **Step 3: Напиши `scripts/arch_detect.py`**

```python
#!/usr/bin/env python3
"""Определяет архитектуру React и NestJS пакетов по каталогам и импортам и печатает JSON для /arch detect.

Признаки архитектур берутся из блока json в разделе «Признаки» каждого refs/arch/<id>.md.
Итог 0.6 доли выполненных структурных условий плюс 0.4 доли импортов между слоями по правилам.
Это эвристика для подсказки человеку. Точные правила проверяет dependency-cruiser.
"""
import argparse
import glob
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

REFS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "refs", "arch")
SKIP_DIRS = {"node_modules", "dist", "build", ".next", ".git", "coverage"}
SOURCE_EXT = (".ts", ".tsx", ".js", ".jsx")
SAMPLE = 300
PICK_SCORE = 0.6
PICK_GAP = 0.15
BONUS = 0.2
STRUCTURE_WEIGHT = 0.6
DEFAULT_GLOBS = ["apps/*", "packages/*", "libs/*"]
# Слои сверху вниз. Импорт разрешен в свой ярус и ниже. Детект видит только направление, не слайсы
LAYERS = {
    "react-fsd": [["app"], ["pages"], ["widgets"], ["features"], ["entities"], ["shared"]],
    "react-feod": [["app"], ["pages"], ["modules"], ["common"]],
    "react-evolution": [["app"], ["features"], ["services"], ["shared"]],
    "react-feature": [["app"], ["features"], ["components", "hooks", "lib", "utils"]],
    "react-clean": [["ui", "presentation"], ["infrastructure"], ["application"], ["domain"]],
    "nest-standard": [],
    "nest-modular-clean": [["presentation"], ["infrastructure"], ["application"], ["domain"]],
    "nest-ddd-cqrs": [["presentation"], ["infrastructure"], ["application"], ["domain"]],
}
IMPORT_RE = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)['"]([^'"]+)['"]""")
SIGNATURE_RE = re.compile(r"^## Признаки\s*\n.*?```json\n(.*?)\n```", re.S | re.M)
PNPM_RE = re.compile(r"""^\s*-\s*['"]?([^'"\n#]+?)['"]?\s*$""", re.M)

Signature = Dict[str, Any]
Candidate = Dict[str, Any]


def _read_json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _read_jsonc(path: str) -> Any:
    # tsconfig из Vite и Nest CLI содержит комментарии и висячие запятые
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    text = re.sub(r"^\s*/\*.*?\*/", "", text, flags=re.M | re.S)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        return json.loads(text)
    except ValueError:
        return None


def deps(package_dir: str) -> Set[str]:
    pkg = _read_json(os.path.join(package_dir, "package.json")) or {}
    found: Set[str] = set()
    for key in ("dependencies", "devDependencies"):
        if isinstance(pkg.get(key), dict):
            found |= set(pkg[key])
    return found


def stack(dep_names: Set[str]) -> Optional[str]:
    if "@nestjs/core" in dep_names:
        return "nest"
    if dep_names & {"react", "next"}:
        return "react"
    return None


def source_root(package_dir: str) -> str:
    src = os.path.join(package_dir, "src")
    return src if os.path.isdir(src) else package_dir


def _workspace_globs(root: str) -> List[str]:
    pkg = _read_json(os.path.join(root, "package.json")) or {}
    workspaces = pkg.get("workspaces")
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages")
    if isinstance(workspaces, list):
        return [w for w in workspaces if isinstance(w, str)]
    pnpm = os.path.join(root, "pnpm-workspace.yaml")
    if os.path.isfile(pnpm):
        with open(pnpm, encoding="utf-8") as f:
            found = PNPM_RE.findall(f.read())
        if found:
            return found
    if any(os.path.isfile(os.path.join(root, name)) for name in ("nx.json", "turbo.json")):
        return list(DEFAULT_GLOBS)
    return []


def find_roots(path: str) -> List[str]:
    root = os.path.abspath(path)
    packages = [root]
    for pattern in _workspace_globs(root):
        if pattern.startswith("!"):
            continue
        for match in glob.glob(os.path.join(root, pattern)):
            parts = set(os.path.relpath(match, root).split(os.sep))
            if os.path.isfile(os.path.join(match, "package.json")) and not parts & SKIP_DIRS:
                packages.append(os.path.abspath(match))
    unique = sorted(set(packages) - {root})
    return [p for p in ([root] + unique) if stack(deps(p))]


def load_signatures(refs_dir: str = REFS) -> Dict[str, Signature]:
    signatures: Dict[str, Signature] = {}
    for path in sorted(glob.glob(os.path.join(refs_dir, "*.md"))):
        arch = os.path.basename(path)[:-3]
        if arch not in LAYERS:
            continue
        with open(path, encoding="utf-8") as f:
            match = SIGNATURE_RE.search(f.read())
        if match:
            signatures[arch] = json.loads(match.group(1))
    return signatures


def _matches(base: str, pattern: str, want_dir: bool) -> List[str]:
    found = []
    for path in glob.glob(os.path.join(base, pattern)):
        if os.path.isdir(path) if want_dir else os.path.isfile(path):
            found.append(os.path.relpath(path, base))
    return sorted(found)


def structure_score(package_dir: str, src: str, dep_names: Set[str], sig: Signature) -> Tuple[float, List[str], List[str]]:
    evidence: List[str] = []
    required = sig.get("requires_dep") or []
    if required and not dep_names & set(required):
        return 0.0, evidence, ["нет зависимости %s" % " или ".join(required)]
    conflicts = ["лишний каталог %s" % hit for pattern in sig.get("dirs_none") or []
                 for hit in _matches(src, pattern, True)]
    if conflicts:
        return 0.0, evidence, conflicts
    total = done = 0
    for pattern in sig.get("dirs_all") or []:
        total += 1
        if _matches(src, pattern, True):
            done += 1
            evidence.append("каталог %s" % pattern)
    for key, want_dir, label in (("dirs_any", True, "каталог"), ("files_any", False, "файл")):
        patterns = sig.get(key) or []
        if not patterns:
            continue
        total += 1
        hits = [hit for pattern in patterns for hit in _matches(src, pattern, want_dir)]
        if hits:
            done += 1
            evidence.append("%s %s" % (label, ", ".join(hits[:3])))
    score = done / total if total else 0.0
    bonus = [hit for pattern in sig.get("bonus_files") or [] for hit in _matches(package_dir, pattern, False)]
    if bonus and score > 0:
        score = min(1.0, score + BONUS)
        evidence.append("конфиг %s" % ", ".join(bonus))
    return score, evidence, []


def source_files(src: str) -> List[str]:
    found: List[str] = []
    for folder, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(SOURCE_EXT) and not name.endswith(".d.ts"):
                found.append(os.path.join(folder, name))
                if len(found) >= SAMPLE:
                    return found
    return found


def _aliases(package_dir: str) -> List[Tuple[str, str]]:
    config = _read_jsonc(os.path.join(package_dir, "tsconfig.json")) or {}
    options = config.get("compilerOptions") or {}
    base = os.path.join(package_dir, options.get("baseUrl") or ".")
    found = []
    for key, targets in (options.get("paths") or {}).items():
        if key.endswith("/*") and targets and str(targets[0]).endswith("/*"):
            found.append((key[:-1], os.path.normpath(os.path.join(base, targets[0][:-1]))))
    return found


def _resolve(spec: str, path: str, aliases: List[Tuple[str, str]]) -> Optional[str]:
    if spec.startswith("."):
        return os.path.normpath(os.path.join(os.path.dirname(path), spec))
    for prefix, target in aliases:
        if spec.startswith(prefix):
            return os.path.normpath(os.path.join(target, spec[len(prefix):]))
    return None


def _layer(rel: str, tiers: List[List[str]]) -> Optional[Tuple[int, str]]:
    for part in rel.split(os.sep):
        for index, tier in enumerate(tiers):
            if part in tier:
                return index, part
    return None


def import_score(package_dir: str, src: str, arch: str, files: List[str]) -> Tuple[float, int]:
    tiers = LAYERS[arch]
    if not tiers:
        return 0.5, 0
    aliases = _aliases(package_dir)
    good = total = 0
    for path in files:
        source = _layer(os.path.relpath(path, src), tiers)
        if source is None:
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        for spec in IMPORT_RE.findall(text):
            target_path = _resolve(spec, path, aliases)
            if target_path is None:
                continue
            rel = os.path.relpath(target_path, src)
            if rel.startswith(".."):
                continue
            target = _layer(rel, tiers)
            if target is None or target[1] == source[1]:
                continue
            total += 1
            if target[0] >= source[0]:
                good += 1
    return (good / total if total else 0.5), total


def pick(candidates: List[Candidate]) -> Optional[str]:
    if not candidates or candidates[0]["score"] < PICK_SCORE:
        return None
    if len(candidates) > 1 and round(candidates[0]["score"] - candidates[1]["score"], 2) < PICK_GAP:
        return None
    return candidates[0]["arch"]


def analyze(package_dir: str, sigs: Dict[str, Signature]) -> Dict[str, Any]:
    dep_names = deps(package_dir)
    kind = stack(dep_names)
    src = source_root(package_dir)
    files = source_files(src)
    candidates: List[Candidate] = []
    for arch, sig in sorted(sigs.items()):
        if not kind or not arch.startswith(kind + "-"):
            continue
        structure, evidence, conflicts = structure_score(package_dir, src, dep_names, sig)
        score = 0.0
        if structure > 0:
            imports, count = import_score(package_dir, src, arch, files)
            if count:
                evidence.append("импортов между слоями %d, по правилам %d%%" % (count, round(imports * 100)))
            weight = float(sig.get("weight", 1.0))
            score = round((STRUCTURE_WEIGHT * structure + (1 - STRUCTURE_WEIGHT) * imports) * weight, 2)
        candidates.append({"arch": arch, "score": score, "evidence": evidence, "conflicts": conflicts})
    candidates.sort(key=lambda c: (-c["score"], c["arch"]))
    return {"root": package_dir, "stack": kind, "src": os.path.relpath(src, package_dir),
            "pick": pick(candidates), "candidates": candidates}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--refs", default=REFS)
    args = parser.parse_args(argv)
    base = os.path.abspath(args.path)
    sigs = load_signatures(args.refs)
    roots = []
    for package_dir in find_roots(base):
        found = analyze(package_dir, sigs)
        found["root"] = os.path.relpath(package_dir, base)
        roots.append(found)
    print(json.dumps({"roots": roots}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Запусти, убедись, что проходит**

Run: `python3 -m unittest tests.test_arch_detect -v`
Expected: PASS. Если `test_evolution_small` дает `None`, проверь, что `react-fsd` получает 0.5 структуры (`shared` есть, `entities` и `widgets` нет), а `react-evolution` 1.0, разрыв больше 0.15.

- [ ] **Step 5: Полный прогон и коммит**

Run: `./tests/run.sh`
Expected: все PASS, живой тест skipped.

```bash
git add scripts/arch_detect.py tests/test_arch_detect.py
```

Выдай человеку: `! git commit -m "feat(arch): detect architecture by structure and imports"`

---

### Task 5: команда `/arch`, скилл `arch-rules`, шаблон steiger

**Files:**
- Create: `commands/arch.md`, `skills/arch-rules/SKILL.md`, `refs/arch/steiger.config.ts`
- Modify: `tests/test_texts.py` (`test_new_commands_are_manual_only`, новый тест команды)

**Interfaces:**
- Consumes: CLI `arch_contract.py` (Task 1), CLI `arch_detect.py` (Task 4), ref и каталог (Task 2, 3).
- Produces: `/arch init | detect | check`, скилл `devkit:arch-rules`, контракт проекта с frontmatter `devkit-arch`, `variant`, `root`, `ignore` и разделом `Долг`.

- [ ] **Step 1: Напиши падающий тест**

В `tests/test_texts.py` в `test_new_commands_are_manual_only` замени кортеж имен на `("grill.md", "handoff.md", "architecture.md", "arch.md")`. Добавь в класс `TextsTest`:

```python
    def test_arch_command(self) -> None:
        with open(os.path.join(ROOT, "commands", "arch.md"), encoding="utf-8") as f:
            text = f.read()
        for word in ("scripts/arch_detect.py", "scripts/arch_contract.py", "--output-type baseline",
                     "steiger-debt", "lint-script", "`[]`", "## init", "## detect", "## check", "ARCHITECTURE.md"):
            self.assertIn(word, text, word)
        with open(os.path.join(ROOT, "skills", "arch-rules", "SKILL.md"), encoding="utf-8") as f:
            skill = f.read()
        self.assertIn("ARCHITECTURE.md", skill)
        self.assertIn("lint:arch", skill)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "refs", "arch", "steiger.config.ts")))
```

- [ ] **Step 2: Запусти, убедись, что падает**

Run: `python3 -m unittest tests.test_texts -v`
Expected: FAIL, `нет arch.md`.

- [ ] **Step 3: Напиши `refs/arch/steiger.config.ts`**

Формат проверен на steiger 0.7.0.

```ts
import { defineConfig } from 'steiger'
import fsd from '@feature-sliced/steiger-plugin'

export default defineConfig([
  ...fsd.configs.recommended,
  {
    // Долг из /arch detect. Правило в warn, пока его нарушения не исправлены
    rules: {},
  },
])
```

- [ ] **Step 4: Напиши `commands/arch.md`**

````markdown
---
description: Выбрать архитектуру React или NestJS, определить ее в существующем коде и проверить границы. init, detect, check.
argument-hint: init | detect | check [путь]
disable-model-invocation: true
---

# Архитектура проекта

Каталог в `${CLAUDE_PLUGIN_ROOT}/refs/arch/catalog.md`, правила каждой архитектуры в `refs/arch/<id>.md` рядом с ним. Говори их словами.

Первое слово `$ARGUMENTS` это подкоманда, второе путь к пакету, по умолчанию текущий каталог. Подкоманды нет, а в пакете есть `ARCHITECTURE.md`, выполняй `check`. Нет и его, спроси, `init` или `detect`.

## Общее

1. Менеджер пакетов по lock-файлу в корне репозитория. `pnpm-lock.yaml` это pnpm, `yarn.lock` это yarn, `bun.lockb` это bun, иначе npm. Запуск бинаря `pnpm exec`, `yarn`, `bunx` или `npx`, ниже везде `npx`.
2. Корень исходников `src`, если он есть, иначе `.`.
3. Ничего не ставь и не перезаписывай без «да». Файл контракта уже есть, покажи дифф с тем, что сгенерировал бы, и спроси.
4. Не коммить.

## Контракт

Файлы, которые `init` и `detect` пишут в пакет.

1. `ARCHITECTURE.md`. Первая строка после frontmatter говорит, что файл сгенерирован `/arch` из devkit и правится руками вместе с `.dependency-cruiser.cjs`.

   ```yaml
   ---
   devkit-arch: <id>
   variant: <small или medium, только react-evolution>
   root: <корень исходников>
   ignore: []
   ---
   ```

   Тело из разделов ref `Дерево`, `Импорты`, `Public API`, `Куда класть`, `Антипаттерны`. Дерево и таблица «Куда класть» на реальных слайсах и модулях проекта, алиасы из `tsconfig.json`. В конце раздел `Долг`. Дата подвязки, число нарушений в baseline, правила steiger в `warn`.
2. `.dependency-cruiser.cjs`. `--tsconfig` только если файл есть.

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py depcruise --arch <id> [--variant <v>] --root <root> [--tsconfig tsconfig.json] > .dependency-cruiser.cjs
   ```

3. `.dependency-cruiser-known-violations.json`, baseline.
4. Для `react-fsd` файл `steiger.config.ts`, копия `${CLAUDE_PLUGIN_ROOT}/refs/arch/steiger.config.ts`.
5. Скрипт `lint:arch` в `package.json` через Edit. `--evo`, если в пакете есть `evo.config.ts`.

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py lint-script --arch <id> --root <root> [--evo]
   ```

6. Строка в `CLAUDE.md` пакета. Нет `CLAUDE.md`, но есть `AGENTS.md`, пиши туда. Нет обоих, создай `CLAUDE.md`.

   ```
   Архитектура описана в ARCHITECTURE.md. Перед созданием или переносом файла читай его.
   ```

7. Зависимости. `npm i -D dependency-cruiser` или `<pm> add -D dependency-cruiser`, для `react-fsd` еще `steiger @feature-sliced/steiger-plugin`. Покажи команду и жди «да».

## init

1. `package.json` пакета. `@nestjs/core` это Nest, `react` или `next` это React. Ни того, ни другого, скажи и остановись.
2. Вопросы из раздела «Вопросы» каталога по одному, у каждого рекомендуемый ответ. Ответ видно из кода или репозитория, не спрашивай, скажи, что взял.
3. Рекомендация по таблице каталога и альтернатива, по фразе почему. Жди выбора. Для `react-evolution` спроси small или medium.
4. Контракт по разделу «Контракт». В пустом корне создай каталоги слоев из раздела `Дерево` ref с `.gitkeep`.
5. Baseline пустой, запиши `[]` в `.dependency-cruiser-known-violations.json`. Без файла `--ignore-known` падает.
6. Запусти `lint:arch`. Упал, разберись до конца команды, это ошибка конфига или кода.

## detect

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_detect.py <путь>`.
2. По каждому корню из `roots`.
   1. `pick` есть. Покажи кандидата, `score`, `evidence` и `conflicts`, спроси подтверждение.
   2. `pick` равен `null`. Покажи 2 лучших кандидата с `evidence` и `conflicts`. Предложи выбрать целевую архитектуру вопросами как в `init`.
3. `roots` пуст, React и Nest не найдены, скажи и остановись.
4. После подтверждения контракт по разделу «Контракт». Для `react-evolution` спроси small или medium.
5. Baseline.

   ```bash
   npx depcruise <root> --output-type baseline > .dependency-cruiser-known-violations.json
   ```

6. Для `react-fsd` долг steiger. Каждое правило из вывода впиши в `rules` в `steiger.config.ts` как `'warn'` и в раздел `Долг`.

   ```bash
   npx steiger <root> --reporter json > "${TMPDIR:-/tmp}/steiger.json"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py steiger-debt < "${TMPDIR:-/tmp}/steiger.json"
   ```

7. Запусти `lint:arch`, он должен пройти.
8. Итог. Число нарушений `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py count < .dependency-cruiser-known-violations.json`, 5 самых частых правил по полю `rule.name` в baseline, правила steiger в `warn`.

## check

1. Нет `lint:arch` в `package.json` пакета, скажи и предложи `/arch detect`. Больше ничего.
2. Запусти `lint:arch`. Новые нарушения списком `файл:строка правило`, к каждому что сделать по разделу «Куда класть» `ARCHITECTURE.md`. depcruise дает только файл, строку найди по импорту.
3. Сравни текущие нарушения с baseline. Текущих меньше, предложи перегенерировать baseline командой из `detect` и обновить число в разделе `Долг`.

   ```bash
   npx depcruise <root> --output-type baseline | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py count
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py count < .dependency-cruiser-known-violations.json
   ```

4. Ничего не правь без «да».

## Стиль

Правила из `${CLAUDE_PLUGIN_ROOT}/refs/style.md`.
````

- [ ] **Step 5: Напиши `skills/arch-rules/SKILL.md`**

```markdown
---
name: arch-rules
description: Создаешь, переносишь или переименовываешь файл в проекте с ARCHITECTURE.md. Раскладка и импорты по контракту.
---

1. Найди ближайший вверх от файла `ARCHITECTURE.md` и прочитай его целиком. Нет файла, скилл не нужен.
2. Id архитектуры в поле `devkit-arch`. Чего-то нет в контракте, читай ref архитектуры, файл `<id>.md` в каталоге `arch` внутри `refs` плагина devkit.
3. Путь нового кода по разделу «Куда класть». Не подходит ни одна строка, спроси, а не придумывай слой.
4. Импорты только по разделу «Импорты». Снаружи модуля или слайса только через его public API.
5. Нужен запрещенный импорт, не обходи правило и не трогай `.dependency-cruiser.cjs` и baseline. Предложи решение из раздела «Антипаттерны» или спроси.
6. После серии правок запусти скрипт `lint:arch` из `package.json`. Упал на твоем коде, почини.

Правила проекта из AGENTS.md и CLAUDE.md важнее, при расхождении следуй им.
```

Путь к ref в скилле словами, а не `refs/arch/<id>.md`. agnix предупреждает о ссылке глубже одного уровня, а `<id>` это шаблон, который стиль-тест не резолвит.

- [ ] **Step 6: Запусти тесты**

Run: `python3 -m unittest tests.test_texts -v`
Expected: PASS. Проверь `test_skill_frontmatter`, описание короче 120 символов и без двоеточия.

- [ ] **Step 7: Коммит**

```bash
git add commands/arch.md skills/arch-rules/SKILL.md refs/arch/steiger.config.ts tests/test_texts.py
```

Выдай человеку: `! git commit -m "feat(arch): /arch command and arch-rules skill"`

---

### Task 6: связки с `/review`, `/check`, справкой и версией

**Files:**
- Modify: `commands/review.md` (раздел «Что собрать», пункт 4)
- Modify: `commands/check.md` (раздел «Что запускаем», пункт 2)
- Modify: `refs/review-react.md:10`, `refs/review-nest.md` (новый пункт 12)
- Modify: `commands/commands.md` (группа «Проверки»)
- Modify: `README.md`, `.claude-plugin/plugin.json`, `tests/test_manifest.py:43-45`
- Test: `tests/test_texts.py`, `tests/test_manifest.py`

**Interfaces:**
- Consumes: контракт проекта из Task 5.
- Produces: версия плагина `0.3.0`.

- [ ] **Step 1: Напиши падающие тесты**

В `tests/test_manifest.py` в `test_plugin_version` замени `"0.2.0"` на `"0.3.0"`. В `tests/test_texts.py` добавь в `TextsTest`:

```python
    def test_review_and_check_read_arch_contract(self) -> None:
        with open(os.path.join(ROOT, "commands", "review.md"), encoding="utf-8") as f:
            review = f.read()
        self.assertIn("ARCHITECTURE.md", review)
        self.assertIn(".dependency-cruiser-known-violations.json", review)
        with open(os.path.join(ROOT, "commands", "check.md"), encoding="utf-8") as f:
            self.assertIn("lint:arch", f.read())
        for name in ("review-react.md", "review-nest.md"):
            with open(os.path.join(ROOT, "refs", name), encoding="utf-8") as f:
                self.assertIn("ARCHITECTURE.md", f.read(), name)
        with open(os.path.join(ROOT, "commands", "commands.md"), encoding="utf-8") as f:
            self.assertIn("/arch init|detect|check", f.read())
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            self.assertIn("/arch", f.read())
```

- [ ] **Step 2: Запусти, убедись, что падает**

Run: `python3 -m unittest tests.test_texts tests.test_manifest -v`
Expected: FAIL в `test_review_and_check_read_arch_contract` и `test_plugin_version`.

- [ ] **Step 3: `commands/review.md`**

В «Что собрать», пункт 4, перед подпунктом `9. Всегда прочитай ... review-shared.md` вставь новый подпункт 9, бывший 9 станет 10:

```markdown
   9. Есть `ARCHITECTURE.md` в пакете измененных файлов, прочитай его. Новые и перенесенные файлы сверь с разделом «Куда класть», импорты с разделом «Импорты». Нарушение это `[архитектура]`. Дифф добавляет записи в `.dependency-cruiser-known-violations.json`, это `[архитектура]` и блокер, новое нарушение спрятали в baseline.
   10. Всегда прочитай `${CLAUDE_PLUGIN_ROOT}/refs/review-shared.md`.
```

- [ ] **Step 4: `commands/check.md`**

В «Что запускаем», пункт 2, после подпункта `6. Монорепо на turbo ...` добавь:

```markdown
   7. Есть скрипт `lint:arch`, запусти его после `lint`. Это границы архитектуры из `ARCHITECTURE.md`. Нет скрипта, depcruise сам не запускай.
```

- [ ] **Step 5: чеклисты ревью**

В `refs/review-react.md` замени пункт 10:

```markdown
10. Границы архитектуры. Есть `ARCHITECTURE.md`, размещение и импорты по нему. Нет, а проект на FSD, импорты только вниз по слоям и через публичный API слайса.
```

В `refs/review-nest.md` добавь в конец:

```markdown
12. Границы модулей. Есть `ARCHITECTURE.md`, проверь по нему. Нет, чужой модуль используется только через экспортируемые провайдеры его `*.module.ts`, контроллер и резолвер не ходят в ORM.
```

- [ ] **Step 6: `commands/commands.md`**

В блоке формата в группе «Проверки» после `/check [база]  lint, типы, тесты` добавь строку:

```
/arch init|detect|check  архитектура проекта
```

- [ ] **Step 7: README и версия**

`.claude-plugin/plugin.json`: `"version": "0.3.0"`, в `description` после `проверки` вставь `, архитектура React и NestJS`.

`README.md`, в таблицу «Команды» после строки `/check` добавь:

```markdown
| `/arch init\|detect\|check [путь]` | выбор архитектуры React или NestJS, детект в существующем коде, проверка границ с baseline |
```

И после раздела «Скиллы» новый раздел:

````markdown
## Архитектура

`/arch` держит проект в одной из 8 архитектур. React: `react-fsd`, `react-feod`, `react-evolution`, `react-feature`, `react-clean`. NestJS: `nest-standard`, `nest-modular-clean`, `nest-ddd-cqrs`. Каталог с матрицей выбора в `refs/arch/catalog.md`.

В проект пишется контракт. `ARCHITECTURE.md`, `.dependency-cruiser.cjs`, baseline `.dependency-cruiser-known-violations.json`, для FSD `steiger.config.ts`, скрипт `lint:arch`. Старые нарушения в baseline не валят проверку, новые валят. Проверка работает в CI и без Claude.

Скилл `arch-rules` раскладывает новый код по контракту, `/review` и `/check` его читают.

```bash
DEVKIT_DEPCRUISE=<путь к depcruise> python3 -m unittest tests.test_arch_live -v
```
````

В разделе «Разработка» строку про живой тест не дублируй, команда выше.

- [ ] **Step 8: Полный прогон**

Run: `./tests/run.sh && npx -y agnix .`
Expected: тесты PASS, agnix без ошибок по `commands/arch.md` и `skills/arch-rules/SKILL.md`.

- [ ] **Step 9: Коммит**

```bash
git add commands/review.md commands/check.md refs/review-react.md refs/review-nest.md commands/commands.md README.md .claude-plugin/plugin.json tests/test_texts.py tests/test_manifest.py
```

Выдай человеку: `! git commit -m "feat(arch): wire arch contract into review, check and docs, bump to 0.3.0"`

---

### Task 7: проверка целиком на живых примерах

**Files:**
- Нет правок в репозитории, если проверка прошла.

**Interfaces:**
- Consumes: все предыдущие задачи.
- Produces: отчет человеку с выводом команд.

- [ ] **Step 1: Живой тест правил**

Run: `DEVKIT_DEPCRUISE="${TMPDIR:-/tmp}/devkit-depcruise/node_modules/.bin/depcruise" python3 -m unittest tests.test_arch_live -v`
Expected: PASS, 2 теста. Нет установки, сделай ее командой из Task 1 Step 7.

- [ ] **Step 2: Сквозной сценарий detect на FSD-примере**

```bash
D="${TMPDIR:-/tmp}/devkit-arch-e2e" && rm -rf "$D" && mkdir -p "$D/src/shared/ui" "$D/src/features/auth" "$D/src/features/cart" "$D/src/entities/user"
cd "$D" && echo '{"name":"e2e","private":true,"dependencies":{"react":"19.0.0"}}' > package.json
echo '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}' > tsconfig.json
echo "export const B=1" > src/shared/ui/index.ts
echo "import {C} from '../cart'; export const A=C" > src/features/auth/index.ts
echo "export const C=1" > src/features/cart/index.ts
echo "import {B} from '@/shared/ui'; export const U=B" > src/entities/user/index.ts
python3 ~/Documents/code/devkit/scripts/arch_detect.py . | head -20
python3 ~/Documents/code/devkit/scripts/arch_contract.py depcruise --arch react-fsd --root src --tsconfig tsconfig.json > .dependency-cruiser.cjs
DC="${TMPDIR:-/tmp}/devkit-depcruise/node_modules/.bin/depcruise"
"$DC" src --output-type baseline > .dependency-cruiser-known-violations.json
python3 ~/Documents/code/devkit/scripts/arch_contract.py count < .dependency-cruiser-known-violations.json
"$DC" src --ignore-known; echo "old=$?"
echo "import {A} from '@/features/auth'; export const Z=A" > src/shared/ui/bad.ts
"$DC" src --ignore-known; echo "new=$?"
```

Expected: детект дает `"pick": "react-fsd"`, `count` печатает `1` (`fsd-cross-slice`), `old=0`, `new` не 0 с `fsd-layers-shared`.

- [ ] **Step 3: Сквозной сценарий на nest new**

```bash
D="${TMPDIR:-/tmp}/devkit-arch-nest" && rm -rf "$D" && mkdir -p "$D/src" && cd "$D"
echo '{"name":"api","dependencies":{"@nestjs/core":"11.0.0"}}' > package.json
for f in main app.module app.controller app.service; do echo "export {}" > "src/$f.ts"; done
python3 ~/Documents/code/devkit/scripts/arch_detect.py . | grep '"pick"'
```

Expected: `"pick": "nest-standard"`.

- [ ] **Step 4: Итог человеку**

Покажи вывод шагов 1 до 3 и итог `./tests/run.sh`. Падения не замазывай, приложи вывод. Временные каталоги в `$TMPDIR` не удаляй без просьбы.
