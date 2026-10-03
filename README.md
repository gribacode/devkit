# devkit

Личный плагин Claude Code для фуллстека React и NestJS. Ревью, описание MR и PR, отработка ревью, учет времени, проверки и защитные хуки.

## Установка

```bash
claude plugin marketplace add ~/Documents/code/devkit
claude plugin install devkit@devkit
```

После установки перезапусти Claude Code. Список команд `/commands`.

С GitHub, когда репозиторий будет опубликован.

```bash
claude plugin marketplace add <github-user>/devkit
claude plugin install devkit@devkit
```

## Команды

| Команда | Что делает |
|---------|------------|
| `/review [база \| ссылка]` | ревью ветки или MR/PR |
| `/pr [база] [ru\|en]` | описание MR/PR |
| `/review-reply <ссылка>` | отработка незакрытых тредов с ответами текстом |
| `/worklog [заметка]` | чекпоинт или созвон в журнал |
| `/report [дата]` | отчет за день по времени |
| `/check [база]` | lint, типы, тесты по затронутым пакетам |
| `/agent-lint [путь]` | agnix по конфигам агента |
| `/commands` | список команд |

## Хуки

| Хук | Событие | Что делает | Выключатель |
|-----|---------|------------|-------------|
| activity | SessionStart, UserPromptSubmit, Stop, SessionEnd | строка в `~/.claude/worklog/<дата>.activity.tsv` | `DEVKIT_ACTIVITY=0` |
| notify | UserPromptSubmit, Notification | уведомление macOS, когда Claude ждет | `DEVKIT_NOTIFY=0` |
| stop | Stop | tsc по правленым файлам, уведомление о готовности | `DEVKIT_TSC=0`, `DEVKIT_NOTIFY=0` |
| guard_bash | PreToolUse Bash | блок rm -rf, commit, push, reset --hard, миграций с потерей данных | `DEVKIT_GUARD=0` |
| guard_secrets | PreToolUse Read Edit Write Grep | блок .env, ключей, ~/.ssh, ~/.aws | `DEVKIT_GUARD=0` |
| format_edit | PostToolUse Edit Write | prettier и eslint --fix по файлу | `DEVKIT_FORMAT=0` |

Заблокированную команду запускай сам через `!` в промпте.

## Разработка

```bash
./tests/run.sh
npx -y agnix .
```

Python 3.9 и только стандартная библиотека.
