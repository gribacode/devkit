# Правила TypeScript

Граница. React в `review-react.md`, Nest в `review-nest.md`, рантайм Node в `stack-node.md`. Здесь только система типов.

1. `any` нет. На границах (ответ API, `JSON.parse`, `catch`) тип `unknown` и сужение через схему (zod, valibot) или type guard.
2. `as` только с комментарием, почему компилятор не выводит тип сам. `as unknown as X` это ошибка дизайна.
3. Non-null `!` только там, где инвариант виден в соседних строках. Иначе явная проверка и ранний выход.
4. `@ts-ignore` нет. `@ts-expect-error` с причиной в той же строке.
5. Литерал, который должен соответствовать типу и сохранить узкий вывод, проверяется через `satisfies`, а не аннотацией.
6. Состояние с вариантами это discriminated union с полем `kind` или `status`, а не набор необязательных полей.
7. `switch` по union исчерпывающий. В `default` присваивание в `never`, чтобы новый вариант ломал сборку.
8. Экспортируемые функции с явным типом возврата. Внутренние полагаются на вывод.
9. `enum` не заводим. Union строковых литералов или объект `as const`.
10. Типы выводятся из источника. `z.infer`, `typeof`, `ReturnType`, сгенерированные типы GraphQL и Prisma. Ручной дубль типа рядом со схемой не пишем.
11. Индексный доступ к массиву и `Record` дает `T | undefined`. Нет `noUncheckedIndexedAccess` в проекте, проверку пишем сами.
12. tsconfig проекта. `strict`, `noUncheckedIndexedAccess`, `noImplicitOverride`, по возможности `exactOptionalPropertyTypes`. Ослабление флага только с комментарием.
13. В тестах частичные объекты через фабрики или `fromPartial` из `@total-typescript/shoehorn`, а не `as Type`.
