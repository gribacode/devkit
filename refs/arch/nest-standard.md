# nest-standard. Модули по фичам из документации Nest

## Когда брать

1. CRUD и средняя логика.
2. Новый проект на Nest, раскладка из `nest new` и документации.
3. Команда знает Nest, обучение не нужно.
4. Перерастает, когда сервисы толстеют от правил. Путь роста в `nest-modular-clean`.

## Дерево

```
src/
  main.ts
  app.module.ts
  users/
    users.module.ts
    users.controller.ts
    users.service.ts
    users.repository.ts     если нужен слой над ORM
    dto/
      create-user.dto.ts
    entities/
      user.entity.ts
  orders/
  common/                   guards, interceptors, filters, pipes, decorators
  config/
```

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `*.controller.ts`, `*.resolver.ts` | свой сервис и `dto` | `nest-controller-no-orm`, `nest-controller-no-repository` |
| `*.service.ts` | свои `repository` и `entities`, ORM, чужие `*.module.ts`, `*.service.ts`, `dto` | `nest-foreign-internals` |
| `common`, `config`, `shared` | только `common`, `config`, `shared` | `nest-common-no-features` |

## Public API

1. Модуль отдает наружу провайдеры из `exports` своего `*.module.ts`.
2. Другой модуль добавляет его в `imports` и инжектит сервис.
3. Controller, `entities` и repository чужого модуля не импортируются. DTO чужого модуля можно, это контракт.

## Куда класть

| новый код | путь |
|-----------|------|
| REST endpoint | `<модуль>/<модуль>.controller.ts` |
| GraphQL резолвер | `<модуль>/<модуль>.resolver.ts` |
| бизнес-правило | `<модуль>/<модуль>.service.ts` |
| запросы к базе | сервис или `<модуль>/<модуль>.repository.ts` |
| входные данные с `class-validator` | `<модуль>/dto/` |
| модель базы | `<модуль>/entities/` или `schema.prisma` |
| guard, pipe, filter, interceptor | `common/` |
| конфиг | `config/` через `ConfigModule` |

## Антипаттерны

1. Контроллер зовет Prisma или репозиторий. Вызов идет через сервис.
2. Сервис на 1000 строк с правилами. Это сигнал перейти в `nest-modular-clean`.
3. Циклы модулей и `forwardRef` без причины. Общее вынеси в отдельный модуль.
4. Импорт `entities` чужого модуля. Попроси данные у его сервиса.

## Признаки

```json
{
  "requires_dep": ["@nestjs/core"],
  "dirs_all": [],
  "dirs_any": [],
  "dirs_none": ["modules", "contexts", "*/domain", "*/infrastructure"],
  "files_any": ["app.module.ts", "*/*.module.ts"],
  "bonus_files": [],
  "weight": 1.0
}
```

## Источники

1. https://docs.nestjs.com/modules
2. https://docs.nestjs.com/cli/usages
