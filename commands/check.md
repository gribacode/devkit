---
description: Прогнать lint, проверку типов, тесты и prisma validate по затронутым пакетам проекта и дать короткую сводку падений.
argument-hint: [база]
---

# Проверка проекта

## Что запускаем

1. Менеджер пакетов по lock-файлу в корне. `pnpm-lock.yaml` это pnpm, `yarn.lock` это yarn, `package-lock.json` это npm, `bun.lockb` это bun.
2. Затронутые пакеты. Файлы из `git diff --name-only <база>...HEAD` и `git status --porcelain`, база из `$ARGUMENTS` или `origin/HEAD`. Для каждого файла ближайший вверх `package.json`. Нет изменений, бери все пакеты из workspace.
3. По каждому пакету скрипты из его `package.json`, какие есть, в таком порядке.
   1. `lint`.
   2. `typecheck`, иначе `type-check`, иначе `tsc --noEmit` если в пакете есть `tsconfig.json`.
   3. `test`. Для jest и vitest без watch, например `pnpm --filter <пакет> test -- --run` для vitest.
4. Есть `schema.prisma` в затронутом пакете, `prisma validate`.
5. Монорепо на turbo и затронуто много пакетов, можно одной командой `pnpm turbo run lint typecheck test --filter=...[<база>]`.

## Вывод

1. Все прошло, одна строка с перечнем того, что гонял.
2. Есть падения. По каждому пакет, команда и до 5 строк сути ошибки, без простыни лога.
3. В конце предложение, что починить первым. Сам не правь, жди ок.

## Стиль

Правила из `${CLAUDE_PLUGIN_ROOT}/refs/style.md`.
