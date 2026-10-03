---
description: Прогнать lint, проверку типов и тесты по затронутым пакетам JS, Python, Docker и nginx и дать короткую сводку падений.
argument-hint: [база]
---

# Проверка проекта

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

## Вывод

1. Все прошло, одна строка с перечнем того, что гонял.
2. Есть падения. По каждому пакет, команда и до 5 строк сути ошибки, без простыни лога.
3. В конце предложение, что починить первым. Сам не правь, жди ок.

## Стиль

Правила из `${CLAUDE_PLUGIN_ROOT}/refs/style.md`.
