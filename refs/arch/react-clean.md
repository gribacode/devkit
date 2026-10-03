# react-clean. Clean и Hexagonal на фронте

## Когда брать

1. Сложная логика на клиенте, редакторы, расчеты, офлайн. Ее нужно тестировать без React.
2. Источник данных меняется, REST на GraphQL, бэкенд на мок.
3. Команда знает порты и адаптеры.
4. Не брать для CRUD поверх API. Слои станут пустыми прокладками.

## Дерево

```
src/
  domain/           сущности и правила, чистый TS
    cart.ts
  application/      сценарии и порты
    add-to-cart.ts
    ports.ts
  infrastructure/   адаптеры портов, http, storage
    cart-api.ts
  ui/               React компоненты и хуки, сборка зависимостей
    cart/
```

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `ui` или `presentation` | `application`, `domain`, `infrastructure` для сборки зависимостей | |
| `infrastructure` | `application`, `domain` | `clean-infrastructure-no-ui` |
| `application` | `domain` | `clean-application-inner` |
| `domain` | ничего из проекта, без React и HTTP-клиентов | `clean-domain-inner`, `clean-domain-no-libs` |

## Public API

1. Сценарий `application` это 1 файл с 1 экспортом.
2. `ui` зовет сценарии. В `infrastructure` он ходит только в точке сборки зависимостей.
3. Порты это интерфейсы в `application/ports.ts`, адаптеры их реализуют.

## Куда класть

| новый код | путь |
|-----------|------|
| бизнес-правило, расчет, тип сущности | `domain/` |
| сценарий пользователя | `application/<сценарий>.ts` |
| интерфейс внешнего мира | `application/ports.ts` |
| http, localStorage, SDK | `infrastructure/` |
| компонент, хук, страница | `ui/` |
| создание адаптеров и передача в сценарии | `ui/`, точка сборки, например провайдер |

## Антипаттерны

1. `domain` импортирует React или axios. Вынеси вызов в адаптер, в домене оставь данные и правила.
2. Сценарий зовет `fetch`. Объяви порт и передай адаптер.
3. Компонент ходит в http мимо сценария. Логика расползается по UI.
4. Слои ради слоев. Сценарий, который только пробрасывает вызов, удали.

## Признаки

```json
{
  "requires_dep": ["react", "next"],
  "dirs_all": ["domain"],
  "dirs_any": ["application", "infrastructure"],
  "dirs_none": ["entities", "widgets", "modules"],
  "files_any": [],
  "bonus_files": [],
  "weight": 1.0
}
```

## Источники

1. https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
2. https://alistair.cockburn.us/hexagonal-architecture/
