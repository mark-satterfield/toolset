---
name: typescript-coding
description: How to write TypeScript and JavaScript (Node and browser) that passes a strict compiler configuration, typescript-eslint strictTypeChecked and stylisticTypeChecked, and Prettier the first time — no any and no unsafe access, unknown plus schema validation at boundaries, indexed access that may be undefined, discriminated unions closed with a never check, readonly data, promises always awaited or handled, only Error thrown, explicit return types on exported functions, ES modules and type-only imports, naming, flat structure, and JavaScript typed with JSDoc under the same rules. Use whenever writing, editing, refactoring, reviewing or testing .ts, .tsx, .mts, .cts, .js, .jsx, .mjs or .cjs files.
user-invocable: true
---

# TypeScript and JavaScript: typed by construction

Write TypeScript as if every value's type were checked at the moment you type it, because it is. The compiler runs
with every strictness flag on and the linter runs the type-aware rule sets, so a value whose type is unknown, a
promise nobody waits for, or an index that may be out of range is an error, not a style point. Write the code that is
correct under those rules first; the checks confirm it and never correct it.

These rules apply to every piece of TypeScript or JavaScript an agent writes, changes or reviews. A reviewer judges
the code against them. For a React web or mobile front end, also load `web-frontend-coding`; for a CDK app written in
TypeScript, also load `cdk-coding`.

## How to read this skill

- Every rule has one form: the instruction, then the reason, then at most one example.
- An example is two labelled code blocks, "Instead of" and "Write". The "Instead of" block shows the habit the rule
  bans. An example illustrates its rule; the rule covers every case its text describes, not only the case shown.
- Examples are shortened: a function in an example has no doc comment unless the rule is about it. Code you write
  carries what this skill requires.
- A rule name in parentheses, such as (`no-floating-promises`), names the compiler option or lint rule that checks the
  same thing. It is there so a finding can be traced to its rule here.

## The configuration this code is written for

Know what is on, because each item changes how ordinary code must be written:

- Compiler: `strict` (all strict checks, including `strictNullChecks` and `noImplicitAny`),
  `noUncheckedIndexedAccess`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`,
  `noImplicitReturns`, `noImplicitOverride`, `forceConsistentCasingInFileNames`, `isolatedModules`.
- Linter: `@eslint/js` recommended, typescript-eslint `strictTypeChecked` and `stylisticTypeChecked` (type-aware: the
  linter knows every value's type).
- Formatter: Prettier defaults: 80 columns, two-space indent, double quotes, semicolons, trailing commas everywhere
  they are valid.

A repository may add options the base leaves open (`target`, `lib`, `jsx`, `paths`); it never weakens these.

## Habits to replace on sight

| Do not | Do instead | Section |
|---|---|---|
| `any`, `as any`, `JSON.parse(text) as Order` | `unknown`, then a schema parse or a type guard | Types |
| `items[0].name` | Check the element exists, or use a method that returns a defined value | Indexed access |
| `doWork();` where `doWork` returns a promise | `await doWork();`, or `void doWork().catch(report)` at a top-level entry | Promises |
| `throw "failed"`, `Promise.reject("failed")` | `throw new Error("...", { cause })` | Errors |
| `value!` | A check that narrows the value | Types |
| `value \|\| fallback` for a value that may be `0` or `""` | `value ?? fallback` | Idioms |
| Deep `if/else` nesting | Guard clauses and early returns | Structure |

## Types

- Never write `any`, in any position: not as an annotation, not as `as any`, not as a generic argument
  (`no-explicit-any`). Never let a value of type `any` flow into anything typed: assigning, calling, indexing,
  returning or passing an `any` is an error (`no-unsafe-assignment`, `no-unsafe-call`, `no-unsafe-member-access`,
  `no-unsafe-return`, `no-unsafe-argument`). The reason: one `any` switches the checker off for everything it touches,
  and the error it hides surfaces at run time.
- Type every value that enters from outside the program as `unknown`: parsed JSON, `fetch` responses, `localStorage`,
  `postMessage` data, environment variables, message payloads, third-party callbacks. Narrow it before use with the
  project's schema library (for example Zod's `schema.parse`) or a type guard. `JSON.parse` returns `any`; assign its
  result to `unknown` immediately.

  Instead of:

  ```ts
  const order = JSON.parse(body) as Order;
  ```

  Write:

  ```ts
  const order: Order = orderSchema.parse(JSON.parse(body) as unknown);
  ```

- Never use a type assertion (`as T`) to claim a type the code has not established. An assertion is a promise the
  checker cannot verify. Narrow instead: `typeof`, `instanceof`, `in`, a discriminant check, or a type guard function
  (`function isOrder(value: unknown): value is Order`). `as const` and `as unknown` are not claims and are fine.
- Never use the non-null assertion `value!` (`no-non-null-assertion`). Check for `undefined` or `null` and handle the
  case; the check narrows the type.
- Never check what the type already rules out (`no-unnecessary-condition`). If a value's type cannot be `null`, do
  not compare it with `null` or use `?.` on it; if it can, the type says so. The reason: an impossible check misleads
  the reader about what values can occur.
- Model a value that is one of several shapes as a discriminated union with a literal `kind` (or `type`) field, and
  close every `switch` over it with a `never` check, so adding a variant makes every unhandled `switch` a compile
  error.

  ```ts
  type PaymentEvent =
    | { readonly kind: "authorized"; readonly amountCents: number }
    | { readonly kind: "refunded"; readonly refundId: string };

  function describe(event: PaymentEvent): string {
    switch (event.kind) {
      case "authorized":
        return `Authorized ${String(event.amountCents)} cents`;
      case "refunded":
        return `Refund ${event.refundId}`;
      default: {
        const unhandled: never = event;
        throw new Error(`Unhandled payment event: ${JSON.stringify(unhandled)}`);
      }
    }
  }
  ```

- Use `interface` for object types and `type` for unions, intersections, tuples and mapped types
  (`consistent-type-definitions`). Write arrays as `T[]` and `readonly T[]` (`array-type`), and a dictionary as
  `Record<Key, Value>` (`consistent-indexed-object-style`).
- Mark data that is not meant to change as `readonly`: `readonly` properties, `readonly T[]`, `ReadonlyMap`,
  `ReadonlySet`, and `as const` for literal tables. Accept the widest read-only type in parameters and return the
  narrowest concrete type. The reason: a function that cannot mutate its input cannot surprise its caller.
- Use string literal unions (`"draft" | "sent"`) or `as const` objects for a closed set of values. Avoid `enum`: it
  emits run-time code and a numeric enum accepts any number.
- Use a generic when a function's input and output types are linked (`function first<T>(items: readonly T[]): T |
  undefined`), and only then: a type parameter used once adds nothing (`no-unnecessary-type-parameters`).
- Annotate signatures; let local variables infer from their initializer. Writing a type on a variable initialized
  with a literal is an error (`no-inferrable-types`), and an explicit type on a local hides a wrong initializer less
  well than inference reveals it. Annotate a local only when its initializer does not express the intended type
  (an empty array, `null` to be filled later).

  Instead of:

  ```ts
  const retryLimit: number = 3;
  const names = [];
  ```

  Write:

  ```ts
  const retryLimit = 3;
  const names: string[] = [];
  ```

- Declare an explicit return type on every exported function and every public method. The reason: the return type is
  the contract; when it is inferred, a change in the body silently changes the contract for every caller.

## Indexed access

`noUncheckedIndexedAccess` makes `array[index]` and `record[key]` have the type `T | undefined`, because the element
may not exist.

- Check the element before use, or use a form that cannot be out of range: `for (const item of items)`,
  `items.map(...)`, `entries()`, destructuring with a check, `Map.get` with a check.

  Instead of:

  ```ts
  const firstName = users[0].name;
  ```

  Write:

  ```ts
  const firstUser = users[0];
  if (firstUser === undefined) {
    return undefined;
  }
  const firstName = firstUser.name;
  ```

- Use a `Map` for a lookup table whose keys are not known at compile time; its `get` returns `V | undefined`
  explicitly. Use a `Record` over a closed union of keys, where every key is known to exist.
- Never index an array with `for...in` (`no-for-in-array`): it iterates string keys, inherited ones included.

## Promises

- Every promise is awaited, returned, or explicitly handled (`no-floating-promises`). The reason: a promise nobody
  waits for loses its rejection, so the failure is never seen and the work may not have finished when the caller
  continues. At a top-level entry where nothing can await (an event handler, module start-up), write
  `void task().catch(reportError)`, stating with `void` that the promise is handled there.
- Never pass an async function where a function returning `void` is expected, such as an event listener or
  `Array.prototype.forEach` (`no-misused-promises`). Wrap it so the promise is handled, or use a `for...of` loop with
  `await` for sequential work and `Promise.all` for concurrent work.

  Instead of:

  ```ts
  button.addEventListener("click", async () => {
    await saveDraft();
  });
  ```

  Write:

  ```ts
  button.addEventListener("click", () => {
    void saveDraft().catch(reportError);
  });
  ```

- Never write `async` on a function that does not `await` (`require-await`), and never `await` a value that is not a
  promise (`await-thenable`).
- Inside `try`, write `return await promise`, so a rejection is caught by that `try` (`return-await`).
- Run independent work together with `Promise.all` (or `Promise.allSettled` when each failure is handled on its
  own), not one `await` after another.
- Give every network call a timeout (`AbortSignal.timeout(ms)`) and pass an `AbortSignal` through long work, so it can
  be cancelled.

## Errors

- Throw only `Error` objects or subclasses (`only-throw-error`), and reject promises only with them
  (`prefer-promise-reject-errors`). Pass the original error as `cause`: `throw new Error("Loading the profile failed",
  { cause: error })`. The reason: only an `Error` carries a stack trace, and `cause` keeps the chain to the original
  failure.
- Treat the caught value as `unknown` (it is, under `strict`) and narrow it before use: `if (error instanceof
  ApiError)`. In a promise `.catch` callback, type the parameter as `unknown` too
  (`use-unknown-in-catch-callback-variable`).
- Never swallow an error. Catch only what you can handle at that point; let everything else propagate. When the
  caught value is not used, omit the binding (`catch {`), since an unused `catch (error)` is an error.
- Define a subclass of `Error` for each failure a caller is expected to handle differently, with a `name` and the
  fields the caller needs.

## Idioms

- Use `??` for a default when `0`, `""` or `false` are valid values (`prefer-nullish-coalescing`), and `?.` for an
  optional chain (`prefer-optional-chain`). `||` replaces every falsy value, not only `null` and `undefined`.
- Use `===` and `!==` only.
- Interpolate only strings into template literals (`restrict-template-expressions`); convert a number or other value
  explicitly with `String(value)` or a formatter (`toFixed`, `Intl.NumberFormat`). The reason: an object interpolates
  as `[object Object]`, `undefined` as `"undefined"`.
- Add numbers to numbers and strings to strings only (`restrict-plus-operands`); build strings with template literals
  or `join`.
- Use `for...of` for iteration that needs `break`, `continue` or `await`, and the array methods (`map`, `filter`,
  `some`, `every`, `find`) for transformation and search. Never mutate an outer array from inside `map`.
- Call a method through its object, or bind it, never as a detached reference (`unbound-method`): `items.map((item) =>
  formatter.format(item))`, not `items.map(formatter.format)`.
- Write a block body for an arrow function whose call returns `void`: `() => { close(); }`, not `() => close()` used
  as a value (`no-confusing-void-expression`).
- Name an unused leading parameter with a leading underscore (`(_event, value) => value`); remove an unused trailing
  one.
- Mark every method that overrides a base class method with `override` (`noImplicitOverride`), so renaming the base
  method breaks the override instead of leaving a dead method.
- End every code path of a function that returns a value with a `return` (`noImplicitReturns`), and end every
  non-empty `case` with `break`, `return` or `throw` (`noFallthroughCasesInSwitch`).

## Naming and modules

- Names: `camelCase` for variables, functions and methods; `PascalCase` for types, interfaces, classes and React
  components; `UPPER_SNAKE_CASE` for module-level constants that are configuration. Name a boolean as a question
  (`isActive`, `hasAccess`). No abbreviations a reader must decode (`usr`, `cfg`, `tmp`, `data`).
- Write ES modules: `import` and `export`, never `require` or `module.exports` in new code.
- Import types with `import type { Order } from "./order.js"` and re-export them with `export type`
  (`isolatedModules`), so the import disappears from the emitted JavaScript.
- Prefer named exports over default exports, so the name is the same at every import site; use a default export only
  where a framework requires one (a Next.js page, an Expo Router screen).
- Keep each module to one concern and under 500 lines. Hoist magic numbers and strings to named constants at the top
  of the module.

## Structure

- Keep control flow flat: handle edge cases, errors and empty states first with guard clauses that return or throw,
  so the main logic stays at the top level of the function. At most one level of nesting in a function.
- Keep each function small enough to read top to bottom without tracking state; extract a condition that combines
  several checks into a named function.
- Pass state explicitly as parameters and return values; no mutable module-level variables.

## JavaScript files

- Treat a `.js`, `.mjs` or `.cjs` file as TypeScript without the syntax: start it with `// @ts-check` where the
  project type-checks JavaScript, and type every function with JSDoc (`@param {string} name`, `@returns
  {Promise<void>}`, `@typedef`). The same rules apply: no implicit `any`, every promise handled, only `Error` thrown,
  `const` by default.
- Use `const`, then `let`; never `var`.

## Doc comments

- Give every exported function, class and type a TSDoc comment (`/** ... */`) that says what it does, what each
  parameter means, what it returns and what it throws. A comment says why or what for, never restates the code.

## The safety net

Where the repository's hooks run the TypeScript compiler, ESLint and Prettier after each edit and at commit, fix every
finding they report and do not run those checks yourself; where no hook runs them, run them on the changed files
before finishing. Formatting is Prettier's: write code in its style (80 columns, double quotes, semicolons, trailing
commas) so its check reports nothing. A finding is fixed in the code; a lint suppression (`eslint-disable`,
`@ts-expect-error`) is written only for a verified limitation of a tool, names one rule, and carries the reason.
