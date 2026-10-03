---
description: Описание MR или PR по шаблону репозитория или по практикам Google, Kubernetes и React. Для своих, рабочих и open source репозиториев. Ничего не создает.
argument-hint: [база] [ru|en]
---

# Описание MR или PR

Сначала прочитай `${CLAUDE_PLUGIN_ROOT}/refs/style.md` и `${CLAUDE_PLUGIN_ROOT}/refs/pr-structure.md`.

## Аргументы

1. В `$ARGUMENTS` слово `ru` или `en` задает язык. Остальное это база.
2. База не задана, удаленная основная ветка `origin/<ветка>` через `git symbolic-ref --short refs/remotes/origin/HEAD`, иначе `origin/main`, `origin/master` или `origin/develop`, что есть. Задана, бери `origin/<ветка>`, если такая есть на remote. Перед диффом `git fetch origin <ветка>`.

## Что собрать

1. `git diff <база>...HEAD --stat`, `git diff <база>...HEAD`, `git log <база>..HEAD --oneline`. Факты берешь из диффа, коммиты только для навигации.
2. Хост по `git remote get-url origin`. GitHub это `gh`, остальное GitLab через `glab` с `GITLAB_HOST=<хост>` для своего хоста.
3. Шаблон репозитория, первый найденный.
   1. `.github/pull_request_template.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/PULL_REQUEST_TEMPLATE/*.md`, `docs/pull_request_template.md`.
   2. `.gitlab/merge_request_templates/*.md`. Несколько шаблонов, бери `Default.md` или ближайший по смыслу.
4. `CONTRIBUTING.md`. Требования к PR, например changeset, DCO подпись, чекбоксы, формат заголовка.
5. Язык, если не задан аргументом.
   1. Последние 10 MR или PR (`glab mr list --merged -P 10` или `gh pr list --state merged -L 10`). Не вышло, последние 20 коммитов основной ветки.
   2. Репозиторий чужой и публичный на github.com, всегда английский.
6. Номер задачи из имени ветки (`ABC-123`), если в заголовках последних MR так принято.

## Что написать

1. Есть шаблон, заполни ровно его. Свои секции не добавляй, чекбоксы отмечай только то, что реально выполнено.
2. Нет шаблона, структура из `pr-structure.md`.
3. Дифф больше 400 измененных строк без lock-файлов, `dist`, сгенерированного кода и снапшотов. Перед описанием одной строкой предложи разбить и назови на какие части.
4. Требования `CONTRIBUTING.md`, которые нельзя выполнить текстом (changeset, подпись), перечисли после блока одной строкой.

## Формат вывода

1. Заголовок и тело в одном блоке кода `markdown`, первая строка блока это заголовок, дальше пустая строка и тело.
2. После блока готовая команда создания, сама ее не запускай. Целевая ветка в ней без префикса `origin/`, например `main`. Тело передается через heredoc.
   1. GitLab `glab mr create --title "<заголовок>" --target-branch <ветка> --description "$(cat <<'EOF' ... EOF)"`.
   2. GitHub `gh pr create --title "<заголовок>" --base <ветка> --body "$(cat <<'EOF' ... EOF)"`.
3. Ничего не создавать, не пушить, не коммитить.

## Стиль

Правила из `${CLAUDE_PLUGIN_ROOT}/refs/style.md` для выбранного языка. Перед отправкой проверь текст.
