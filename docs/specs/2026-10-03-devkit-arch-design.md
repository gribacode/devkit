# devkit 0.3: выбор, детект и контроль архитектуры для React и NestJS

Дата: 2026-10-03
Статус: дизайн согласован, ждет ревью спека
Основа: `docs/specs/2026-10-03-devkit-design.md`, `docs/specs/2026-10-03-devkit-stacks-design.md`

## Зачем

1. На старте проекта выбрать архитектуру по понятной матрице, а не по моде.
2. В существующем проекте определить, по какой архитектуре он живет, и подвязаться к ней.
3. Проект строго следует выбранной архитектуре. Правила записаны в документе в репозитории и проверяются линтером в CI, без Claude тоже.
4. Агент раскладывает новый код по правилам проекта, а `/review` ловит нарушения.

Ограничения. Ни одной новой записи в `hooks.json`. Python 3.9 и только stdlib для скриптов devkit. Ничего не ставится в проект без согласия человека.

## Решения, принятые при обсуждении

1. Контроль: документ плюс линтер в проекте. Хука на правку нет.
2. Каталог 0.3: React FSD, FEOD, Evolution Design, feature-based, Clean/Hexagonal. NestJS standard (раскладка из `nest new` и документации), modular + Clean/Hexagonal, DDD + CQRS. Всего 8.
3. Существующий проект с нарушениями подвязывается через baseline и храповик. Старые нарушения не валят проверку, новые валят, число старых только уменьшается.
4. Подход к контролю гибридный (C). dependency-cruiser обязателен для всех архитектур и отвечает за импорты и baseline. steiger добавляется для FSD. Только dependency-cruiser (A) отклонен, он не видит структуру FSD. Родные линтеры для всех (B) отклонены, у них три разных механизма baseline, а у steiger своего нет.
5. Одна команда `/arch` с подкомандами `init`, `detect`, `check`. Имя `/architecture` уже занято углублением модулей.
6. `edlint` (Evolution Design) версии 0.0.9 `/arch init` не ставит. Если в проекте уже есть `evo.config.ts`, `lint:arch` запускает и его. Импорты ED проверяет dependency-cruiser.
7. Шаблоны правил хранятся в JSON (`depcruise/<id>.json`), а не в `.cjs`. Python из stdlib их читает, подставляет корень исходников и пишет в проект самодостаточный `.dependency-cruiser.cjs`. CI проекта не зависит от devkit. Правила всех 8 архитектур проверены на dependency-cruiser 18.5.0 на примерах с нарушением каждого правила.

## Ориентиры

| Источник | Что взято |
|----------|-----------|
| feature-sliced.design, steiger | слои FSD, правила слайсов, линтер структуры |
| feod.dev, статья Спортмастер Lab на Хабре | слои FEOD, фрактальные модули, public API через index |
| github.com/ep-community/evolution-design | слои ED, модификации small и medium, `edlint` |
| alan2207/bulletproof-react | feature-based раскладка, запрет импорта фичи из фичи |
| docs.nestjs.com, `@nestjs/cqrs` | модули Nest, команды, запросы, события |
| dependency-cruiser | правила `forbidden`, `--output-type baseline`, `--ignore-known` |

Мнения людей в `catalog.md` подписаны как мнения и со ссылкой. Евгений Паромов: курс по FSD, доклад на Merge 2024 о трех недостатках FSD, затем Evolution Design. Принцип не усложнять структуру раньше, чем ее окупит размер проекта, идет в каталог без имен: подтвержденного источника у позиций Климова и ThePrimeagen нет. Matt Pocock: глубокие модули, уже есть в `refs/codebase-design.md`. Без подтвержденного источника имя человека в ref не пишется.

## Структура, что добавляется

```
devkit/
  commands/
    arch.md                      новое: /arch init | detect | check
    review.md check.md commands.md   правки
  skills/
    arch-rules/SKILL.md          новое: автовызов при создании и переносе файлов
  refs/
    arch/
      catalog.md                 матрица выбора
      react-fsd.md react-feod.md react-evolution.md react-feature.md react-clean.md
      nest-standard.md nest-modular-clean.md nest-ddd-cqrs.md
      depcruise/<id>.json        правила forbidden на каждый id, 8 файлов, плюс react-evolution.medium.json
      depcruise/base.json        общие опции: exclude, no-circular, no-orphans
      steiger.config.ts          шаблон для react-fsd
    review-react.md review-nest.md   правки
  scripts/
    arch_detect.py               новое: детект
    arch_contract.py             новое: сборка .dependency-cruiser.cjs, счет baseline, долг steiger, скрипт lint:arch
  tests/
    test_arch_detect.py test_arch_refs.py test_arch_contract.py   новое
    test_arch_live.py            новое: правила на настоящем depcruise, пропускается без DEVKIT_DEPCRUISE
  README.md .claude-plugin/plugin.json      версия 0.3.0, раздел про /arch
```

## Ref архитектуры

Каждый `refs/arch/<id>.md` содержит ровно эти разделы в этом порядке, заголовками второго уровня. Их проверяет `test_arch_refs.py`.

1. `## Когда брать`. От 3 до 5 признаков за и против.
2. `## Дерево`. Каноническая структура с примером на 2 фичи.
3. `## Импорты`. Таблица `откуда | можно импортировать`. Имена слоев в таблице совпадают с именами в `depcruise/<id>.json`.
4. `## Public API`. Что экспортирует `index.ts`, запрет deep import.
5. `## Куда класть`. Таблица `новый код | путь`. Главный раздел для агента.
6. `## Антипаттерны`. Ошибка и как чинить.
7. `## Признаки`. Структурные и импортные признаки для детекта в машинно-читаемом блоке (см. ниже).
8. `## Источники`. Только проверенные ссылки.

### Правила по архитектурам

| id | Импорты | Особое |
|----|---------|--------|
| react-fsd | `app > pages > widgets > features > entities > shared`, только вниз. Слайсы одного слоя друг друга не импортируют, кроме `entities` через `@x`. Снаружи слайса только через `index` | steiger для структуры. В Next.js App Router слой `app` FSD живет в `src/app`, роутер в корневом `app/` реэкспортирует страницы из `src/pages`, как в доке FSD |
| react-feod | `app > pages > modules > common`. Модуль импортирует другой модуль только через его `index`. `common` не импортирует ничего из проекта. `global` не импортируется | вложенные модули подчиняются тем же правилам |
| react-evolution | `app > features > services > shared`. `features` и `services` не импортируют `app`. `services` не импортирует `features`. В medium фича не импортирует фичу. В small можно | модификация (`small` или `medium`) пишется во frontmatter контракта и выбирает набор правил. `services` в small необязателен |
| react-feature | `app > features > shared` (`components`, `hooks`, `lib`, `api`, `types`). Фича не импортирует фичу, композиция в `app` и роутах | как Bulletproof React |
| react-clean | `ui > application > domain`, `infrastructure > application, domain`. `domain` не импортирует `react`, `fetch`-клиенты и `infrastructure` | порты в `application`, адаптеры в `infrastructure` |
| nest-standard | плоский модуль фичи `src/<x>/` (`<x>.module.ts`, `<x>.controller.ts`, `<x>.service.ts`, `dto/`, `entities/`). Controller и resolver импортируют только сервисы и DTO, не ORM и не репозитории. Модуль берет у другого модуля только `*.module.ts` и `*.service.ts`, не controller и не `entities` напрямую. DTO другого модуля можно. `common/` и `config/` не импортируют модули фич | раскладка по умолчанию из `nest new` и доки Nest. Путь роста в nest-modular-clean без смены границ модулей |
| nest-modular-clean | модуль из `src/modules/<x>` импортирует другой модуль только через его `index.ts` (модуль Nest и экспортируемые провайдеры). Внутри модуля `presentation > application > domain`, `infrastructure > application, domain`. `@prisma/client` и ORM только в `infrastructure`. `shared` без бизнес-логики | `domain` не импортирует `@nestjs/*` |
| nest-ddd-cqrs | контекст из `src/contexts/<x>` видит другой контекст только через его `contracts/` (события, DTO, интерфейсы). `domain` не импортирует `@nestjs/*`, ORM и `infrastructure`. Handler вызывает домен и репозиторий, бизнес-правил в handler нет | агрегат меняется только через свои методы, это проверяет `/review`, не линтер |

Все конфиги включают `no-circular` и `no-orphans` в `warn`.

### Блок признаков

В разделе `## Признаки` один блок кода `json`, его читает `arch_detect.py`:

```json
{
  "requires_dep": ["react"],
  "dirs_all": ["shared"],
  "dirs_any": ["entities", "widgets"],
  "dirs_none": ["services", "modules", "domain"],
  "files_any": [],
  "bonus_files": ["steiger.config.*"],
  "weight": 1.0
}
```

1. `requires_dep` выполнен, если в `dependencies` или `devDependencies` есть хотя бы один пакет из списка.
2. Все пути это glob относительно корня исходников (`src`, если есть, иначе корень пакета). `dirs_*` совпадают только с каталогами, `files_any` с файлами. `bonus_files` ищутся от корня пакета, там лежат `steiger.config.ts` и `evo.config.ts`. Пример для nest-modular-clean `modules/*/domain`, для nest-standard `files_any: ["app.module.ts", "*/*.module.ts"]` и `dirs_none: ["modules", "contexts", "*/domain", "*/infrastructure"]`.
3. Условия это каждый элемент `dirs_all`, весь `dirs_any` как одно условие и весь `files_any` как одно условие, если список не пуст. `structure = выполнено / всего`. `bonus_files` добавляет 0.2, максимум 1.0. Невыполненный `requires_dep` или найденный `dirs_none` дает 0.

## `catalog.md`

1. 5 вопросов: размер фронт-команды, сложность домена, срок жизни, где живет бизнес-логика (клиент или сервер), монорепо.
2. Таблица `ответы > рекомендация > альтернатива`.
3. По умолчанию для MVP и проектов до 12 человеко-месяцев рекомендуется react-feature или react-evolution small. Путь роста: feature > evolution medium или FSD. Для Nest по умолчанию nest-standard. nest-modular-clean, когда в сервисах копится бизнес-логика, которую хочется тестировать без Nest и ORM. nest-ddd-cqrs только при сложном домене и нескольких командах.
4. Раздел «Кто так делает» с источниками по правилам из «Ориентиров».

## Контракт в проекте

Единственный источник правды для агента, `/review` и `/arch check`.

1. `ARCHITECTURE.md` в корне пакета. Frontmatter:

   ```yaml
   devkit-arch: react-evolution
   variant: medium        # только для react-evolution
   root: src
   ignore: ["src/legacy/**"]
   ```

   Тело собирается из ref: разделы `Дерево`, `Импорты`, `Public API`, `Куда класть`, `Антипаттерны`, плюс реальные слайсы и алиасы проекта. В конце раздел `Долг` со списком правил steiger в `warn` и числом нарушений в baseline на дату подвязки.
2. `.dependency-cruiser.cjs`: собирает `arch_contract.py depcruise` из `base.json`, `<id>.json` и варианта, с `tsConfig` из проекта, чтобы алиасы `@/` и `paths` резолвились.
3. `.dependency-cruiser-known-violations.json`: baseline, коммитится.
4. Для react-fsd `steiger.config.ts`.
5. Скрипт в `package.json`: `"lint:arch": "depcruise <root> --ignore-known"`, для FSD плюс `&& steiger <root>`, при наличии `evo.config.ts` плюс `&& edlint`.
6. Строка в `CLAUDE.md` или `AGENTS.md` пакета (что есть, иначе в `CLAUDE.md`): `Архитектура описана в ARCHITECTURE.md. Перед созданием или переносом файла читай его.`
7. В монорепо у каждого пакета свой контракт.

## `/arch`

### `init [путь]`

1. Определяет стек по `package.json`: `react` или `next` значит фронт, `@nestjs/core` значит бэк. Нет ни того, ни другого, команда останавливается.
2. Задает вопросы из `catalog.md` по одному, с рекомендуемым ответом.
3. Дает рекомендацию и альтернативу с причиной. Ждет выбора.
4. Показывает список файлов контракта и команду установки (`npm i -D dependency-cruiser`, для FSD плюс `steiger @feature-sliced/steiger-plugin`, менеджер пакетов по lock-файлу). Ставит только после «да».
5. Пишет контракт. В пустом проекте создает каталоги слоев с `.gitkeep`.
6. Пишет пустой baseline `[]` в `.dependency-cruiser-known-violations.json`, без файла `--ignore-known` падает. Запускает `lint:arch`. В новом проекте нарушений быть не должно.

### `detect [путь]`

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_detect.py <путь>` дает JSON.
2. У лучшего кандидата `score >= 0.6` и отрыв от второго не меньше `0.15`. Команда показывает кандидата, доказательства и конфликты и просит подтвердить.
3. Иначе показывает 2 лучших кандидата и предлагает выбрать целевую архитектуру как в `init`.
4. После подтверждения пишет контракт, ставит инструменты с согласия, снимает baseline: `depcruise <root> --output-type baseline > .dependency-cruiser-known-violations.json`.
5. Для FSD прогоняет steiger. Правила с нарушениями переводит в `warn` в `steiger.config.ts` и записывает в раздел `Долг`.
6. Печатает число нарушений в baseline и 5 самых частых правил.

### `check [путь]`

1. Нет `lint:arch` в `package.json`, команда говорит об этом и предлагает `/arch detect`. Больше ничего не делает.
2. Запускает `lint:arch`. Новые нарушения выводит списком `файл:строка правило > что сделать` по разделу `Куда класть` контракта.
3. Считает текущие нарушения `depcruise <root> --output-type baseline | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_contract.py count` и нарушения в baseline `arch_contract.py count < .dependency-cruiser-known-violations.json`. Текущих меньше, предлагает перегенерировать baseline.

### Существующие файлы

`ARCHITECTURE.md`, `.dependency-cruiser.cjs` или `steiger.config.ts` уже есть, команда не перезаписывает. Показывает дифф с тем, что сгенерировала бы, и спрашивает.

## `arch_detect.py`

Чистые функции плюс `main`, как `scripts/worklog_blocks.py`.

1. `find_roots(path)`. Пакет с `package.json`. При `workspaces`, `pnpm-workspace.yaml`, `nx.json` или `turbo.json` обходит пакеты по globs из них. Пропускает `node_modules`, `dist`, `.next`, `build`. Анализируются только пакеты с `react`, `next` или `@nestjs/core`.
2. `load_signatures(refs_dir)`. Читает блок `json` из раздела `## Признаки` каждого ref.
3. `structure_score(src, deps, sig)`. По правилам из «Блока признаков».
4. `import_score(root, arch)`. Выборка до 300 файлов `.ts .tsx .js .jsx` из корня исходников. Регулярками извлекает относительные импорты и импорты через алиасы из `tsconfig.json` `paths`. Слой файла это первый сегмент пути, который есть в `LAYERS[arch]`. Импорт между разными слоями соответствует архитектуре, если слой цели стоит в списке ниже слоя источника. Нет ни одного импорта между слоями, `imports = 0.5`. `LAYERS` лежит в скрипте, тест проверяет, что каждый слой упомянут в разделе `Импорты` ref. Детект это эвристика, точные правила только у depcruise.
5. Итоговый `score = 0.6 * structure + 0.4 * imports` (`* weight`).
6. Вывод: `{"roots": [{"root", "stack", "src", "pick", "candidates": [{"arch", "score", "evidence": [...], "conflicts": [...]}]}]}`. Кандидаты отсортированы по `score`, только архитектуры своего стека. `pick` это id лучшего кандидата, если выполнен порог из `/arch detect`, иначе `null`.
7. `nx.json` или `turbo.json` без `workspaces` и без `pnpm-workspace.yaml` дают globs `apps/*`, `packages/*`, `libs/*`.

## Связки с существующим

1. Скилл `arch-rules`. Описание: создаешь, переносишь или переименовываешь файл в проекте с `ARCHITECTURE.md`. Тело: прочитай `ARCHITECTURE.md` пакета, при нужде ref из `${CLAUDE_PLUGIN_ROOT}/refs/arch/<id>.md`, клади код по разделу `Куда класть`, импортируй только по разделу `Импорты`, после серии правок запусти `lint:arch`.
2. `/check` запускает `lint:arch`, если скрипт есть.
3. `/review` читает `ARCHITECTURE.md` и проверяет размещение новых файлов и импорты. Рост `.dependency-cruiser-known-violations.json` в диффе это блокер `[архитектура]`. Пункт 10 в `review-react.md` заменяется общим: границы по `ARCHITECTURE.md`, если он есть. В `review-nest.md` добавляется пункт о границах модулей и контекстов.
4. `commands.md` и README перечисляют `/arch`.

## Ошибки и крайние случаи

1. Нет бинаря `depcruise`, `/arch check` и `/check` пропускают проверку с одной строкой об этом.
2. Алиасы. `.dependency-cruiser.cjs` всегда получает `options.tsConfig.fileName`, если есть `tsconfig.json`.
3. Смешанная структура. Детект показывает конфликты, команда не выбирает сама.
4. Next.js App Router. Описано в ref react-fsd и react-feature. Детект не принимает корневой `app/` Next за слой.
5. Проект без `src`. Корень исходников это корень пакета, `root: .` во frontmatter. `arch_contract.py` убирает префикс корня из правил, `^__ROOT__/features/` становится `^features/`.

## Тесты

1. `test_arch_detect.py`. Фикстуры-деревья во временном каталоге на каждую из 8 архитектур, проект из `nest new` без доработок дает nest-standard, смесь FSD и features, монорепо с FSD и Nest, пустой проект, Next с корневым `app/`. Проверяется лучший кандидат и срабатывание порога.
2. `test_arch_refs.py`. Каждый ref содержит 8 разделов в порядке. У каждого id есть `depcruise/<id>.json`. Блок признаков парсится как JSON. Слои из `LAYERS` встречаются в разделе `Импорты`. Каждое правило из json упомянуто в ref по имени.
3. `test_texts.py` проверяет `refs/*.md`. Glob расширяется до `refs/**/*.md`, чтобы под стиль попали `refs/arch/`.
4. Ручная проверка на этапе плана. Сгенерированный конфиг на маленьком FSD-примере и на Nest-примере ловит нарушение, а после снятия baseline это нарушение не валит `lint:arch`, новое валит.

## Что не входит в 0.3

1. Автоматический перенос кода между архитектурами.
2. Хук на правку.
3. eslint-plugin-boundaries.
4. Vue, Angular, Svelte.
5. Установка `edlint`.
6. Свой линтер.
