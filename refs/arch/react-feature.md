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
