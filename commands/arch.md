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
2. Все команды ниже запускай из каталога пакета, `cd <пакет>`. В монорепо у каждого пакета свой контракт. `<root>` это корень исходников относительно пакета, `src`, если он есть, иначе `.`.
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

   `ignore` это globs от корня пакета, например `src/legacy/**`. Каждый идет в конфиг флагом `--ignore`.

   Тело из разделов ref `Дерево`, `Импорты`, `Public API`, `Куда класть`, `Антипаттерны`. Дерево и таблица «Куда класть» на реальных слайсах и модулях проекта, алиасы из `tsconfig.json`. В конце раздел `Долг`. Дата подвязки, число нарушений в baseline, правила steiger в `warn`.
2. `.dependency-cruiser.cjs`. `--tsconfig` это вывод `arch_contract.py tsconfig`, пустой вывод значит без флага. У Vite алиасы лежат в `tsconfig.app.json`, с корневым `tsconfig.json` depcruise их не резолвит. `--parser swc`, если `arch_contract.py parser` напечатал `swc`. dependency-cruiser 18 разбирает TS только через typescript ниже 7, с TypeScript 7 он молча не видит `.ts` и проверка всегда зеленая.

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py tsconfig .
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py parser .
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py depcruise --arch <id> [--variant <v>] --root <root> [--tsconfig <файл>] [--parser swc] [--ignore <glob>] > .dependency-cruiser.cjs
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

7. Зависимости. `npm i -D dependency-cruiser` или `<pm> add -D dependency-cruiser`, для `react-fsd` еще `steiger @feature-sliced/steiger-plugin`, для парсера swc еще `@swc/core`. Покажи команду и жди «да».
8. Видимость. depcruise должен видеть модули и резолвить свои импорты, иначе зеленая проверка ничего не значит. Модулей 0 или `unresolved` дает больше 0, покажи список, проверь парсер и tsconfig из пункта 2 и не заканчивай команду. В корне без единого исходника видимость не проверяй, depcruise падает с `TS18003`, проверь после первого файла.

   ```bash
   npx depcruise <root> --output-type json > "${TMPDIR:-/tmp}/depcruise.json"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py modules < "${TMPDIR:-/tmp}/depcruise.json"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py unresolved < "${TMPDIR:-/tmp}/depcruise.json"
   ```

## init

1. `package.json` пакета. `@nestjs/core` это Nest, `react` или `next` это React. Ни того, ни другого, скажи и остановись.
2. Вопросы из раздела «Вопросы» каталога по одному, у каждого рекомендуемый ответ. Ответ видно из кода или репозитория, не спрашивай, скажи, что взял.
3. Рекомендация по таблице каталога и альтернатива, по фразе почему. Жди выбора. Для `react-evolution` спроси small или medium.
4. Контракт по разделу «Контракт». В пустом корне создай каталоги слоев из раздела `Дерево` ref с `.gitkeep`.
5. Baseline пустой, запиши `[]` в `.dependency-cruiser-known-violations.json`. Без файла `--ignore-known` падает.
6. Корень пустой, только `.gitkeep`, скажи, что видимость и `lint:arch` проверятся после первого файла, и закончи. Иначе проверь видимость по пункту 8 «Контракта» и запусти `lint:arch`. Упал, разберись до конца команды, это ошибка конфига или кода.

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

7. Проверь видимость по пункту 8 «Контракта». Запусти `lint:arch`, он должен пройти.
8. Итог. Число нарушений `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py count < .dependency-cruiser-known-violations.json`, 5 самых частых правил по полю `rule.name` в baseline, правила steiger в `warn`.

## check

1. Нет `lint:arch` в `package.json` пакета, скажи и предложи `/arch detect`. Больше ничего. Есть скрипт, но нет бинаря `node_modules/.bin/depcruise`, скажи одной строкой «нет бинаря depcruise, поставь зависимости» и остановись.
2. Проверь видимость по пункту 8 «Контракта». Ноль модулей, скажи и предложи пересобрать конфиг с парсером из `arch_contract.py parser`. Запусти `lint:arch`. Новые нарушения списком `файл:строка правило`, к каждому что сделать по разделу «Куда класть» `ARCHITECTURE.md`. depcruise дает только файл, строку найди по импорту.
3. Сравни текущие нарушения с baseline. Текущих меньше, предложи перегенерировать baseline командой из `detect` и обновить число в разделе `Долг`.

   ```bash
   npx depcruise <root> --output-type baseline | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py count
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py count < .dependency-cruiser-known-violations.json
   ```

4. Ничего не правь без «да».

## Стиль

Правила из `${CLAUDE_PLUGIN_ROOT}/refs/style.md`.
