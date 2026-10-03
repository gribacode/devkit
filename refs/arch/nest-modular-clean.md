# nest-modular-clean. Модульный монолит с чистыми слоями

## Когда брать

1. В сервисах копятся правила, их хочется тестировать без Nest и базы.
2. Модули крупные, у каждого свои сценарии и хранилище.
3. ORM или внешний клиент могут смениться.
4. Не брать для CRUD. Слои станут прокладками, хватит `nest-standard`.

## Дерево

```
src/
  main.ts
  app.module.ts
  modules/
    users/
      index.ts              public API, модуль и экспортируемые типы
      users.module.ts
      presentation/         controllers, resolvers, dto
      application/          сервисы сценариев, порты
      domain/               сущности и правила без Nest и ORM
      infrastructure/       репозитории на ORM, внешние клиенты
    billing/
  shared/                   prisma, config, guards без бизнес-логики
```

## Импорты

| откуда | можно импортировать | правило |
|--------|---------------------|---------|
| `presentation` | `application`, `domain` | `nmc-presentation-no-infrastructure` |
| `application` | `domain` | `nmc-application-inner` |
| `domain` | ничего из модуля, без `@nestjs/*` и ORM | `nmc-domain-inner`, `nmc-domain-no-framework` |
| `infrastructure` | `application`, `domain`, ORM | `nmc-orm-in-infrastructure` |
| другой модуль | только его `index.ts` | `nmc-public-api` |
| `shared` | без `modules` | `nmc-shared-no-modules` |

ORM разрешен в `infrastructure` модулей и в `shared`, `database`, `prisma` в корне, там живет `PrismaService`. `*.module.ts` связывает порты с адаптерами и может импортировать любой слой своего модуля.

## Public API

1. `modules/<x>/index.ts` экспортирует Nest-модуль и типы, нужные другим модулям.
2. Сервис чужого модуля доступен через `exports` его модуля и DI.
3. Порты объявлены в `application`, реализации в `infrastructure`, связь через токен провайдера в `*.module.ts`.

## Куда класть

| новый код | путь |
|-----------|------|
| endpoint, резолвер, DTO | `modules/<x>/presentation/` |
| сценарий | `modules/<x>/application/<сценарий>.service.ts` |
| порт репозитория или клиента | `modules/<x>/application/ports/` |
| правило, сущность, value object | `modules/<x>/domain/` |
| репозиторий на Prisma или TypeORM | `modules/<x>/infrastructure/` |
| `PrismaService`, конфиг, общие guards | `shared/` |

## Антипаттерны

1. `@Injectable` или Prisma в `domain`. Домен это классы и функции без фреймворка.
2. `application` импортирует `PrismaClient`. Объяви порт, реализуй в `infrastructure`.
3. Импорт `modules/billing/domain/...` из `users`. Только через `index.ts` и DI.
4. Бизнес-логика в `shared`. Перенеси в модуль, который ею владеет.

## Признаки

```json
{
  "requires_dep": ["@nestjs/core"],
  "dirs_all": ["modules"],
  "dirs_any": ["modules/*/domain", "modules/*/application", "modules/*/infrastructure"],
  "dirs_none": ["contexts"],
  "files_any": [],
  "bonus_files": [],
  "weight": 1.0
}
```

## Источники

1. https://docs.nestjs.com/modules
2. https://docs.nestjs.com/fundamentals/custom-providers
3. https://alistair.cockburn.us/hexagonal-architecture/
