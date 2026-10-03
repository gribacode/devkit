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
