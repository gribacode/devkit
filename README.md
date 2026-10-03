# devkit

Личный плагин Claude Code для фуллстека на TypeScript, Node.js и Python с Docker и nginx. Ревью, описание MR и PR, отработка ревью, учет времени, проверки, конспекты в Obsidian и защитные хуки.

## Установка

```bash
claude plugin marketplace add gribacode/devkit
claude plugin install devkit@devkit
```

Из локального клона.

```bash
git clone https://github.com/gribacode/devkit.git
claude plugin marketplace add ./devkit
claude plugin install devkit@devkit
```

После установки перезапусти Claude Code. Список команд `/commands`.

## Команды

| Команда | Что делает |
|---------|------------|
| `/review [база \| ссылка]` | ревью ветки или MR/PR |
| `/pr [база] [ru\|en]` | описание MR/PR |
| `/review-reply <ссылка>` | отработка незакрытых тредов с ответами текстом |
| `/worklog [заметка]` | чекпоинт или созвон в журнал |
| `/report [дата]` | отчет за день по времени |
| `/check [база]` | lint, типы, тесты по затронутым пакетам JS, Python, Docker, nginx |
| `/arch init\|detect\|check [путь]` | выбор архитектуры React или NestJS, детект в существующем коде, проверка границ с baseline |
| `/grill [тема]` | допрос по плану раундами с рекомендуемыми ответами |
| `/architecture [путь]` | HTML-отчет с кандидатами на углубление модулей и разбор выбранного |
| `/handoff [задача]` | документ для следующей сессии в `$TMPDIR` |
| `/agent-lint [путь]` | agnix по конфигам агента |
| `/note <тема> [что увидел]` | конспект в хранилище Obsidian по правилам хранилища, в фоне |
| `/commands` | список команд |

`/note` пишет в `$DEVKIT_NOTES`, по умолчанию `~/Documents/code/notes`. В хранилище должны лежать `Как писать конспекты.md` и `Шаблоны/Конспект.md`, команда берет правила оттуда.

## Хуки

| Хук | Событие | Что делает | Выключатель |
|-----|---------|------------|-------------|
| activity | SessionStart, UserPromptSubmit, Stop, SessionEnd | строка в `~/.claude/worklog/<дата>.activity.tsv` | `DEVKIT_ACTIVITY=0` |
| notify | UserPromptSubmit, Notification | уведомление macOS, когда Claude ждет | `DEVKIT_NOTIFY=0` |
| stop | Stop | tsc и pyright/mypy по правленым файлам, тесты по флагу, уведомление о готовности | `DEVKIT_TSC=0`, `DEVKIT_TYPES=0`, `DEVKIT_TESTS=1`, `DEVKIT_NOTIFY=0` |
| guard_bash | PreToolUse Bash | блок rm -rf, commit, push, reset --hard, миграций с потерей данных, удаления томов docker, публикации пакетов | `DEVKIT_GUARD=0` |
| guard_secrets | PreToolUse Read Edit Write Grep | блок .env, ключей, ~/.ssh, ~/.aws | `DEVKIT_GUARD=0` |
| format_edit | PostToolUse Edit Write | biome или prettier, oxlint, eslint для JS и TS, ruff для Python, hadolint, compose config, gixy | `DEVKIT_FORMAT=0` |

Заблокированную команду запускай сам через `!` в промпте.

Инструменты запускаются, только если они настроены в проекте или установлены. Для Docker и nginx поставь их сам.

```bash
brew install hadolint
pipx install gixy-ng
```

## Скиллы

Срабатывают сами по ситуации. `typescript`, `node`, `python`, `docker`, `nginx` ведут на правила в `refs/stack-*.md`, те же правила читает `/review`. `codebase-design` про глубокие модули и швы. `writing-for-agents` про CLAUDE.md и AGENTS.md.

`/grill`, `/handoff`, `/architecture`, `codebase-design` и `writing-for-agents` адаптированы из [mattpocock/skills](https://github.com/mattpocock/skills) (MIT).

## Архитектура

`/arch` держит проект в одной из 8 архитектур. React: `react-fsd`, `react-feod`, `react-evolution`, `react-feature`, `react-clean`. NestJS: `nest-standard`, `nest-modular-clean`, `nest-ddd-cqrs`. Каталог с матрицей выбора в `refs/arch/catalog.md`.

В проект пишется контракт. `ARCHITECTURE.md`, `.dependency-cruiser.cjs`, baseline `.dependency-cruiser-known-violations.json`, для FSD `steiger.config.ts`, скрипт `lint:arch`. Старые нарушения в baseline не валят проверку, новые валят. Проверка работает в CI и без Claude.

Скилл `arch-rules` раскладывает новый код по контракту, `/review` и `/check` его читают.

```bash
DEVKIT_DEPCRUISE=<путь к depcruise> python3 -m unittest tests.test_arch_live -v
```

## Разработка

```bash
./tests/run.sh
npx -y agnix .
```

Python 3.9 и только стандартная библиотека.
