# nest-ddd-cqrs. Bounded contexts и CQRS

## Когда брать

1. Сложный домен с инвариантами и процессами.
2. Несколько команд, у каждой свой контекст.
3. Части системы общаются событиями.
4. Не брать для CRUD. Команды и handlers удвоят код без пользы.

## Дерево

```
src/
  main.ts
  app.module.ts
  contexts/
    billing/
      billing.module.ts
      contracts/            события, DTO и интерфейсы для других контекстов
        invoice-paid.event.ts
      domain/               агрегаты, value objects, доменные события
        invoice.aggregate.ts
      application/
        commands/           команда и ее handler
        queries/
        event-handlers/
        ports/
      infrastructure/       репозитории, мапперы, внешние клиенты
      presentation/         controllers, resolvers
    users/
  shared/                   CqrsModule, prisma, общие типы
```

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `presentation` | `application` через `CommandBus` и `QueryBus`, `contracts` | |
| `application` | `domain`, `contracts`, свои `ports` | `ddd-application-inner` |
| `domain` | ничего из контекста, без `@nestjs/*` и ORM | `ddd-domain-inner`, `ddd-domain-no-framework` |
| `infrastructure` | `application`, `domain`, ORM | |
| другой контекст | только его `contracts` | `ddd-context-contracts` |
| `shared` | без `contexts` | `ddd-shared-no-contexts` |

## Public API

1. Наружу контекст отдает только `contracts`. События, классы запросов, DTO, интерфейсы.
2. Контексты не импортируют модули друг друга. Связь через `EventBus` и `QueryBus` с классами из `contracts`.
3. `app.module.ts` собирает модули контекстов.

## Куда класть

| новый код | путь |
|-----------|------|
| изменение состояния | `application/commands/<команда>.command.ts` и `.handler.ts` |
| чтение | `application/queries/` |
| реакция на событие другого контекста | `application/event-handlers/` |
| инвариант, правило | метод агрегата в `domain/` |
| событие для других контекстов | `contracts/` |
| репозиторий, маппер | `infrastructure/` |

## Антипаттерны

1. Бизнес-правило в handler. Handler грузит агрегат, зовет метод, сохраняет.
2. Агрегат меняют сеттерами снаружи. Состояние меняется только методами агрегата, это проверяет ревью.
3. Импорт `domain` чужого контекста. Нужные данные отдает событие или запрос из `contracts`.
4. CQRS для CRUD. Простое чтение и запись остаются в `nest-standard`.

## Признаки

```json
{
  "requires_dep": ["@nestjs/cqrs"],
  "dirs_all": ["contexts"],
  "dirs_any": ["contexts/*/domain", "contexts/*/application", "contexts/*/contracts"],
  "dirs_none": [],
  "files_any": [],
  "bonus_files": [],
  "weight": 1.0
}
```

## Источники

1. https://docs.nestjs.com/recipes/cqrs
2. https://martinfowler.com/bliki/BoundedContext.html
