# react-fsd. Feature-Sliced Design

## Когда брать

1. Фронт-команда от 3 человек, проект живет дольше года, фич больше 10.
2. Нужна общая карта проекта и внешняя документация, по которой новичок разбирается сам.
3. Команда готова к дисциплине. Каждый новый файл требует решения о слое и слайсе.
4. Не брать для MVP и прототипа. Короткий проект не окупит слои, бери `react-feature` или `react-evolution` small.

## Дерево

```
src/
  app/              провайдеры, роутер, глобальные стили
  pages/
    cart/           ui/ model/ index.ts
  widgets/
    header/         ui/ index.ts
  features/
    add-to-cart/    ui/ model/ api/ index.ts
    auth-by-email/
  entities/
    product/        ui/ model/ api/ @x/ index.ts
    user/
  shared/
    ui/ api/ lib/ config/
```

Next.js App Router. Корневой `app/` занят роутером, код FSD живет в `src/`, слой `app` FSD это `src/app`. Файлы роутера только реэкспортируют страницы из `src/pages`. Пустой корневой `pages/` с `README.md` не дает Next включить старый роутер. Корень исходников `src`.

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `app` | все слои ниже | |
| `pages` | `widgets`, `features`, `entities`, `shared` | `fsd-layers-pages` |
| `widgets` | `features`, `entities`, `shared` | `fsd-layers-widgets` |
| `features` | `entities`, `shared` | `fsd-layers-features` |
| `entities` | `shared`, другую сущность только через `@x` | `fsd-layers-entities` |
| `shared` | только `shared` | `fsd-layers-shared` |

Слайс не импортирует соседний слайс своего слоя, правило `fsd-cross-slice`. Исключение это `entities/<x>/@x/<потребитель>.ts`. Циклы и файлы без импортеров ловят `no-circular` и `no-orphans` в `warn`. Структуру слайсов и сегментов проверяет steiger.

## Public API

1. У каждого слайса `index.ts`. Он экспортирует только то, что нужно снаружи.
2. Снаружи слайса импорт только из его `index.ts`, правило `fsd-public-api`. `@/features/auth/model/store` запрещен, `@/features/auth` можно.
3. Сущность отдает API другой сущности через `entities/<x>/@x/<потребитель>.ts`.
4. У `shared` нет общего индекса. Индекс у каждого сегмента, `@/shared/ui`, `@/shared/lib/date`.

## Куда класть

| новый код | путь |
|-----------|------|
| страница роута | `pages/<страница>/ui/` |
| крупный блок из нескольких фич, нужен нескольким страницам | `widgets/<блок>/ui/` |
| действие пользователя с бизнес-ценностью, форма, кнопка с логикой | `features/<действие>/` |
| бизнес-сущность, ее тип, стор, запросы, карточка | `entities/<сущность>/` |
| UI-кит, http-клиент, утилиты без бизнес-смысла | `shared/<сегмент>/` |
| провайдеры, роутер, глобальные стили | `app/` |
| код нужен только одной странице | внутри этой страницы, заранее не выносить |

## Антипаттерны

1. Фича импортирует фичу. Собери их в виджете или странице, общий кусок спусти в `entities` или `shared`.
2. Все подряд в `features`. Кнопка без бизнес-логики живет в `shared/ui`, просмотр сущности в `entities`.
3. Бизнес-логика в `shared`. Код знает про пользователя или заказ, значит он в `entities`.
4. Импорт в обход `index.ts`. Добавь нужный экспорт в public API слайса.
5. Слайс из 1 файла, который нужен 1 странице. Держи код в странице, пока он не понадобится второй раз.

## Признаки

```json
{
  "requires_dep": ["react", "next"],
  "dirs_all": ["shared"],
  "dirs_any": ["entities", "widgets"],
  "dirs_none": ["services", "modules", "domain"],
  "files_any": [],
  "bonus_files": ["steiger.config.*"],
  "weight": 1.0
}
```

## Источники

1. https://feature-sliced.design/docs/get-started/overview
2. https://feature-sliced.design/docs/guides/tech/with-nextjs
3. https://github.com/feature-sliced/steiger
