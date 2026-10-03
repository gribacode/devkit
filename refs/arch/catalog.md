# Каталог архитектур

Выбор на старте и путь роста. Правила каждой архитектуры в `<id>.md` рядом.

## Вопросы

1. Сколько человек будет писать этот пакет через год. 1 или 2, от 3 до 6, больше 6 или несколько команд.
2. Насколько сложен домен. CRUD и формы, есть правила и состояния, много правил, инвариантов и процессов.
3. Сколько проект проживет. Прототип или MVP, от полугода до 2 лет, дольше.
4. Где живет бизнес-логика. В основном на сервере, или заметная часть на клиенте, офлайн, расчеты, редакторы.
5. Это пакет монорепо, где соседние пакеты уже выбрали архитектуру. Да, бери ту же для того же стека, если нет причины иначе.

## Рекомендации

### React

| ответы | рекомендация | альтернатива |
|--------|--------------|--------------|
| 1 или 2 человека, прототип или MVP | `react-feature` | `react-evolution` small |
| 1 или 2 человека, проект надолго | `react-evolution` small | `react-feature` |
| от 3 до 6, CRUD или средний домен | `react-evolution` medium | `react-fsd` |
| от 3 до 6, нужен стандарт с внешней документацией | `react-fsd` | `react-evolution` medium |
| больше 6 или несколько команд, микрофронтенды | `react-feod` | `react-fsd` |
| сложная логика на клиенте, тесты без UI | `react-clean` | `react-evolution` medium |

Путь роста. `react-feature` переходит в `react-evolution` small почти без переноса, `components`, `hooks`, `lib` уезжают в `shared`. small переходит в medium, когда фичи начинают мешать друг другу. Переход в FSD это перенос кода по слоям, его планируют отдельно.

### NestJS

| ответы | рекомендация | альтернатива |
|--------|--------------|--------------|
| CRUD, любая команда | `nest-standard` | |
| в сервисах копятся правила, их хочется тестировать без Nest и ORM | `nest-modular-clean` | `nest-standard` |
| сложный домен, несколько команд, события между частями системы | `nest-ddd-cqrs` | `nest-modular-clean` |

Путь роста. `nest-standard` переходит в `nest-modular-clean` без смены границ модулей, модуль переезжает в `modules/<x>` и делится на слои. `nest-ddd-cqrs` берут, когда модули стали bounded contexts со своим языком.

## Кто так делает

Решение по таблице выше. Ниже происхождение вариантов.

1. FSD. Стандарт с документацией и линтером steiger. https://feature-sliced.design
2. Евгений Паромов вел курс по FSD, на Merge 2024 разобрал 3 главных недостатка FSD, затем с сообществом сделал Evolution Design. https://skolkovo2024.mergeconf.ru/speakers/development/frontend/paromov и https://github.com/ep-community/evolution-design
3. FEOD от Спортмастер Lab, упрощенный FSD с фрактальными модулями. https://habr.com/ru/companies/sportmaster_lab/articles/972410/
4. Bulletproof React, самый известный шаблон раскладки по фичам. https://github.com/alan2207/bulletproof-react
5. Matt Pocock. Глубокие модули и маленькие интерфейсы это ось дизайна внутри любой архитектуры, см. `refs/codebase-design.md`. https://github.com/mattpocock/skills
6. Структуру не усложняют раньше, чем ее окупит размер проекта. Поэтому для MVP таблица дает `react-feature` и `nest-standard`.
7. NestJS. Модули по фичам из документации https://docs.nestjs.com/modules, CQRS из https://docs.nestjs.com/recipes/cqrs
