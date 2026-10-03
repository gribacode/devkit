# devkit 0.2: стеки Python, Node.js, Docker, nginx, строгий TS и скиллы из aihero

Дата: 2026-10-03
Статус: дизайн согласован, ждет ревью спека
Основа: `docs/specs/2026-10-03-devkit-design.md`

## Зачем

1. Правка `.py`, `Dockerfile`, compose-файла или конфига nginx получает такую же автопроверку, какую сейчас получает `.ts`.
2. `/check` и `/review` понимают Python, Node.js, Docker и nginx на одном уровне.
3. Работа с JS и TS становится строже: biome и oxlint рядом с eslint, тесты по правленым файлам, правила строгих типов, дизайн модулей.
4. Из mattpocock/skills (aihero.dev) взяты полезные скиллы без дублей с superpowers и командами devkit.

Ограничения. Харнесс не тяжелеет: ни одной новой записи в `hooks.json`, один процесс python на правку, как сейчас. Правила в контексте не противоречат друг другу и установленным скиллам (`superpowers`, `vercel-react-best-practices`, `nestjs-expert`, `pyright-lsp`).

## Решения, принятые при обсуждении

1. Все четыре стека поддерживаются одинаково глубоко.
2. Хуки расширяются таблицей стеков внутри существующих `format_edit.py` и `stop.py` (подход A). Отдельные скрипты на стек и декларативный конфиг отклонены: первые дают 4 или 5 процессов на правку, второй это лишний фреймворк.
3. Инструмент запускается, только если у проекта есть его конфиг или локальный бинарь. Иначе хук молча выходит, чтобы не переформатировать чужой репозиторий.
4. Знания по стеку живут в одном `refs/stack-<стек>.md`. Его читают и `/review`, и тонкий скилл с автовызовом при написании кода.
5. Тесты по правленым файлам на Stop выключены по умолчанию, включаются `DEVKIT_TESTS=1`. Причина: TDD из superpowers нарочно оставляет красный тест, блокирующий хук с ним спорит.
6. Скиллы aihero адаптируются внутрь devkit, а не ставятся плагином mattpocock целиком. Плагин целиком принес бы около 30 скиллов, среди них `tdd`, `diagnosing-bugs`, `code-review`, `pr`, которые дублируют superpowers и `/review`, `/pr`.
7. Из aihero берутся `grill-me` (с `grilling`), `handoff`, `writing-for-agents`, `improve-codebase-architecture`, `codebase-design`. `domain-modeling` не берется, поэтому `/architecture` использует `GLOSSARY.md` и ADR, только если они уже есть.
8. `nginx -t` не идет в хук. Ему нужны include и резолв upstream из compose, локально это ненадежно. Он идет в `/check` через docker.

## Ориентиры

| Источник | Что взято |
|----------|-----------|
| mattpocock/skills (MIT) | `grilling`, `handoff`, `writing-for-agents`, `improve-codebase-architecture` с `HTML-REPORT.md`, `codebase-design` с `DEEPENING.md` и `DESIGN-IT-TWICE.md`, идея shoehorn для тестов |
| hadolint, gixy | статический анализ Dockerfile и конфигов nginx |
| biome, oxlint, ruff | быстрые линтеры и форматтеры, если проект их выбрал |

## Структура, что добавляется

```
devkit/
  commands/
    grill.md               новое
    handoff.md             новое
    architecture.md        новое
    review.md check.md agent-lint.md commands.md   правки
  skills/
    typescript/SKILL.md
    node/SKILL.md
    python/SKILL.md
    docker/SKILL.md
    nginx/SKILL.md
    codebase-design/SKILL.md DEEPENING.md DESIGN-IT-TWICE.md
    writing-for-agents/SKILL.md SKILL-MECHANICS.md
  refs/
    stack-typescript.md stack-node.md stack-python.md stack-docker.md stack-nginx.md
    codebase-design.md     словарь и принципы, общий для скилла, /review и /architecture
    grilling.md            правила допроса, общие для /grill и /architecture
    architecture-report.md шаблон HTML-отчета
  hooks/
    _stacks.py             новое: правила выбора инструментов по файлу
    format_edit.py stop.py guard_bash.py _common.py   правки
```

Подкаталоги `skills/` плагин регистрирует как скиллы `devkit:<имя>`. Отдельной регистрации в `plugin.json` не требуется, это проверяется на этапе плана вместе с подстановкой `${CLAUDE_PLUGIN_ROOT}` в тексте скилла. Если подстановки нет, скилл ссылается на ref относительным путем от своего каталога.

## Хуки

### `_stacks.py`

Чистые функции без побочных эффектов, их легко тестировать.

1. `kind(path)` возвращает `js`, `python`, `dockerfile`, `compose`, `nginx` или `None`.
   1. `js`: `.js .jsx .ts .tsx .mjs .cjs`. Для prettier дополнительно `.json .css .scss .md`, как сейчас.
   2. `python`: `.py`, `.pyi`.
   3. `dockerfile`: имя `Dockerfile`, `Dockerfile.*`, `*.Dockerfile`, `Containerfile`.
   4. `compose`: `compose.y(a)ml`, `compose.*.y(a)ml`, `docker-compose*.y(a)ml`.
   5. `nginx`: `.conf`, если имя начинается с `nginx` или путь содержит каталог `nginx`, `conf.d`, `sites-available`, `sites-enabled`.
2. `js_tools(path)` решает, чем форматировать JS. Есть `biome.json` или `biome.jsonc` вверх по дереву и `node_modules/.bin/biome`, это biome, prettier и eslint не запускаются. Иначе prettier, затем oxlint (если есть `.oxlintrc.json` и бинарь), затем eslint, как сейчас.
3. `python_bin(path, name)` ищет бинарь в `.venv/bin` и `venv/bin` вверх по дереву, затем в PATH.
4. `ruff_configured(path)`: есть `ruff.toml`, `.ruff.toml` или `[tool.ruff]` в ближайшем `pyproject.toml`.
5. `python_typechecker(path)`: `pyrightconfig.json` или `[tool.pyright]` дает pyright, `mypy.ini`, `.mypy.ini` или `[tool.mypy]` дает mypy, иначе `None`. Без настроенной проверки типов ничего не запускается.

### `format_edit.py`

Пропуск каталогов (`node_modules`, `dist`, `build`, `.next`, `coverage`, `__generated__`) расширяется на `.venv`, `venv`, `__pycache__`, `.mypy_cache`, `.ruff_cache`.

| Вид | Что делает | Блок exit 2 |
|-----|------------|-------------|
| js, biome | `biome check --write <файл>`, таймаут 30 секунд | остались ошибки, до 20 строк |
| js, без biome | prettier как сейчас, `oxlint --fix <файл>` при конфиге, `eslint --fix` как сейчас | ошибки oxlint или eslint, до 20 строк |
| python | при `ruff_configured`: `ruff format <файл>`, затем `ruff check --fix <файл>`, таймауты 15 секунд | остались ошибки ruff check |
| dockerfile | `hadolint --failure-threshold error <файл>`, если hadolint есть в PATH | ошибки уровня error |
| compose | `docker compose -f <файл> config -q` из каталога файла, если docker есть в PATH, таймаут 15 секунд | ненулевой код, до 20 строк stderr |
| nginx | `gixy <файл>`, если gixy есть в PATH | находки уровня High |

Учет правленых файлов для Stop: `.ts`, `.tsx`, а теперь и `.py`. При `DEVKIT_TESTS=1` также `.js`, `.jsx`, `.mjs`, `.cjs`, чтобы найти связанные тесты.

Коды выхода линтеров разбираются как сейчас у eslint: блок только на код «есть ошибки в файле». Поломка конфига или падение инструмента не вешается на Claude.

### `stop.py`

Порядок проверок. Первая с ошибками блокирует Stop через `{"decision":"block","reason":...}`, остальные в этом проходе не запускаются. При `stop_hook_active` все проверки пропускаются, как сейчас.

1. tsc по правленым `.ts`/`.tsx`, как сейчас. Выключатель `DEVKIT_TSC=0`.
2. pyright или mypy по правленым `.py`, сгруппированным по корню проекта (ближайший `pyproject.toml`). Команда `pyright <файлы>` или `mypy <файлы>`, бинарь через `python_bin`. Ошибки фильтруются по правленым файлам, до 20 строк. Таймаут 90 секунд. Выключатель `DEVKIT_TYPES=0`.
3. Только при `DEVKIT_TESTS=1`. JS: `vitest related --run <файлы>` при наличии `node_modules/.bin/vitest`, иначе `jest --findRelatedTests <файлы> --passWithNoTests`. Python: `pytest` по тестам, найденным для правленых модулей по имени `test_<модуль>.py`, и по самим правленым тестам. Таймаут 90 секунд. В причине блока до 30 строк хвоста вывода.

Таймаут хука в `hooks.json` поднимается со 120 до 240 секунд, чтобы вместить три проверки.

### `guard_bash.py`

Новые блоки:

1. `docker compose down` с `-v` или `--volumes`, `docker-compose down -v`. Удаляет тома с данными БД.
2. `docker volume rm`, `docker volume prune`, `docker system prune`.
3. `npm publish`, `pnpm publish`, `yarn publish`, `yarn npm publish`, `twine upload`, `uv publish`, `poetry publish`.

### Выключатели

`DEVKIT_FORMAT=0` выключает все форматтеры и линтеры после правки. `DEVKIT_TSC=0` выключает tsc. Новые: `DEVKIT_TYPES=0` выключает pyright и mypy, `DEVKIT_TESTS=1` включает тесты.

## refs по стекам

Формат как у `review-react.md`: 10 до 15 пронумерованных правил, каждое это требование, а не совет. В шапке граница, чтобы правила не пересекались.

| Файл | Граница | Темы |
|------|---------|------|
| `stack-typescript.md` | React в `review-react.md`, Nest в `review-nest.md` | `any`, `as`, `!`, `@ts-ignore` только с комментарием почему. `unknown` на границах и сужение. `satisfies`. Discriminated unions и исчерпывающий `switch` через `never`. Флаги `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`. В тестах вместо `as` частичные данные через shoehorn или фабрики |
| `stack-node.md` | Nest в `review-nest.md` | Нет висящих промисов и unhandled rejection. Таймаут и `AbortSignal` у внешних вызовов. Стримы через `pipeline`, backpressure. Graceful shutdown по SIGTERM. Конфиг из env с валидацией на старте. Нет синхронного IO в обработчиках запросов. ESM и CJS не смешиваются |
| `stack-python.md` | | Type hints на публичных функциях. Нет голого `except` и `except Exception: pass`. Ресурсы через `with`. В async нет блокирующих вызовов. Валидация на границах через pydantic или dataclass. Нет изменяемых значений по умолчанию. pytest-фикстуры и `parametrize`. Зависимости через uv или poetry с lock-файлом |
| `stack-docker.md` | | Multi-stage. Базовый образ с тегом версии, без `latest`. Порядок слоев ради кеша, сначала манифесты зависимостей. `.dockerignore`. Non-root `USER`. Секреты не попадают в слои и `ARG`. `HEALTHCHECK`. В compose `depends_on` с `condition: service_healthy`, именованные тома для данных, порты БД не торчат наружу |
| `stack-nginx.md` | | `server_tokens off`. Заголовки безопасности. Слэш в `proxy_pass` и что он делает с путем. `X-Forwarded-*` и `real_ip`. SPA fallback через `try_files`. Долгий кеш статики с хешем, `no-cache` для `index.html`. gzip. `client_max_body_size`. Upgrade для websocket. `resolver`, когда upstream задан переменной |

`refs/codebase-design.md` это адаптация `codebase-design`: словарь (модуль, интерфейс, глубина, шов, адаптер, рычаг, локальность), тест удаления, «один адаптер это гипотетический шов, два это настоящий», приемы тестируемости.

## Скиллы

Все с автовызовом. Описание одной строкой до 120 символов, начинается с ситуации. Тело короткое.

| Скилл | Срабатывает | Тело |
|-------|-------------|------|
| `typescript` | пишешь или правишь TS | прочитай `refs/stack-typescript.md`. Правила проекта (AGENTS.md, CLAUDE.md, конфиг линтера) важнее |
| `node` | серверный код на Node.js | `refs/stack-node.md`, для Nest дополнительно `nestjs-expert`, если он есть |
| `python` | пишешь или правишь Python | `refs/stack-python.md` |
| `docker` | Dockerfile или compose | `refs/stack-docker.md` |
| `nginx` | конфиг nginx | `refs/stack-nginx.md` |
| `codebase-design` | проектируешь модуль, интерфейс или шов, делаешь код тестируемым | `refs/codebase-design.md`, по ссылкам `DEEPENING.md` и `DESIGN-IT-TWICE.md` рядом |
| `writing-for-agents` | правишь CLAUDE.md, AGENTS.md или документ, который читает агент | адаптированный текст. В описании прямо: для скиллов используй `superpowers:writing-skills` |

Скиллов для React и Nest нет, их закрывают установленные `vercel-react-best-practices` и `nestjs-expert`.

## Новые команды

Все только с ручным вызовом, как остальные команды devkit. Текст на русском по `refs/style.md`, эмодзи из оригиналов убраны.

### `/grill [тема]`

1. Правила в `refs/grilling.md`: дерево решений, вопросы раундами по фронтиру, у каждого номер и рекомендуемый ответ, между вопросами разделитель.
2. Факты агент находит сам, при необходимости субагентом. Решения задает человеку.
3. Конец, когда фронтир пуст. До подтверждения человеком ничего не делать.

### `/handoff [для чего следующая сессия]`

1. Документ в `$TMPDIR/handoff-<YYYYMMDD-HHMM>.md`, не в репозиторий. Путь печатается.
2. Что уже лежит в спеках, планах, коммитах, MR, не копируется, дается путь или ссылка.
3. Раздел «Какие скиллы и команды вызвать».
4. Секреты и персональные данные вычищаются.

### `/architecture [путь]`

1. Субагент обходит код (или путь из аргумента) и ищет места трения: мелкие модули, протекающие швы, нетестируемые интерфейсы. Тест удаления к каждому подозрению.
2. HTML-отчет по `refs/architecture-report.md` в `$TMPDIR/architecture-<время>.html`, Tailwind и Mermaid с CDN, открыть через `open`. У каждого кандидата файлы, проблема, решение, выгода, схема до и после, сила рекомендации. В конце лучший кандидат.
3. Словарь из `refs/codebase-design.md`. `GLOSSARY.md` и `docs/adr/` используются, если есть, не создаются.
4. После отчета вопрос, какого кандидата разобрать, затем допрос по `refs/grilling.md`.

## Правки существующих команд

### `/review`

Раздел «Чеклисты по стеку» расширяется. Читать только то, что задел дифф.

1. `.ts`, `.tsx` дают `stack-typescript.md`.
2. `.py` дает `stack-python.md`.
3. `Dockerfile*`, `*.Dockerfile`, compose-файлы дают `stack-docker.md`.
4. Конфиги nginx по правилу `kind` дают `stack-nginx.md`.
5. Не-React код с импортами `node:`, `express`, `fastify`, `koa` или обращениями к `process.` дает `stack-node.md`. Nest-код получает и его, и `review-nest.md`.
6. Ось «дизайн модулей» по `codebase-design.md` только если дифф добавляет модуль или меняет экспортируемый интерфейс.

### `/check`

1. Python. Раннер по lock-файлу: `uv.lock` это `uv run`, `poetry.lock` это `poetry run`, иначе `.venv/bin`. Затем `ruff check`, pyright или mypy по конфигу, `pytest`.
2. Docker. `hadolint` по измененным Dockerfile, `docker compose config -q` по измененным compose-файлам.
3. nginx. `docker run --rm -v <каталог>:/etc/nginx/<куда> nginx:<версия из Dockerfile, иначе alpine> nginx -t`. Ошибки `host not found in upstream` отфильтровать и упомянуть одной строкой. Нет docker, шаг пропустить с пометкой.
4. JS. Нет скрипта `lint`, но есть конфиг biome или oxlint, запустить его.

### `/agent-lint`

После agnix смысловой проход по правилам из `${CLAUDE_PLUGIN_ROOT}/skills/writing-for-agents/SKILL.md`: формулировки указателей и описаний, лишнее в постоянно загруженном контексте, ступени иерархии. Находки в том же формате, отдельным блоком.

### `/commands`, README, `plugin.json`

Новые команды, скиллы и выключатели в шпаргалке и README. Версия плагина 0.2.0, сейчас 0.1.0.

## Атрибуция

В начале каждого адаптированного файла строка `Адаптировано из mattpocock/skills (MIT), <путь в репозитории>`.

## Тестирование

1. `test_format_edit.py`: на каждый вид фейковый бинарь в PATH или `node_modules/.bin`, проверка аргументов и кода выхода. Отдельно: biome выключает prettier и eslint, ruff без конфига не запускается, нет бинаря дает молчаливый exit 0, файл в `.venv` пропускается.
2. `test_stop.py`: pyright блокирует при ошибке в правленом файле и игнорирует ошибки в чужих. `DEVKIT_TYPES=0` выключает. Тесты не запускаются без `DEVKIT_TESTS=1`, с ним падение vitest блокирует.
3. `test_stacks.py`: таблица путей для `kind`, выбор проверки типов Python по конфигам.
4. `test_guard_bash.py`: блок `docker compose down -v`, `docker volume prune`, `npm publish`. Пропуск `docker compose down`, `docker compose up -d`, `npm pack`.
5. `test_texts.py` распространяется на `skills/**/*.md`, проверяет фронтматтер `name` и `description` у каждого `SKILL.md`, длину описания до 120 символов и ссылки `${CLAUDE_PLUGIN_ROOT}`.
6. `npx -y agnix .` без ошибок.
7. Ручная проверка: правка `.py` с ошибкой ruff в проекте с `[tool.ruff]` дает фидбек, правка compose с битым YAML дает фидбек, скилл `devkit:python` виден в списке скиллов.

## Вне scope

1. Скиллы для React и Nest.
2. `domain-modeling`, `tdd`, `diagnosing-bugs`, `code-review`, `pr`, `triage`, `to-spec`, `to-tickets` из aihero.
3. Установка hadolint, gixy, ruff и pyright плагином. README подсказывает `brew install hadolint` и `pipx install gixy-ng`.
4. `nginx -t` в хуке.
5. Тесты на Stop по умолчанию.
