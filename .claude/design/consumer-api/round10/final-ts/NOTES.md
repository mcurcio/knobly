# Round 10 final, TypeScript: NestJS, and only NestJS

Copied from `../ts-nest/` (the judge's pick), polished. **Model:** Nest's legacy decorators plus
`reflect-metadata`. Package = `@Module`; kind of block = scope class (a controller); directive =
method (a route handler); value = decorated parameter whose **annotation is the only place its type
is written**; handed-in things = providers. Docs: [controllers](https://docs.nestjs.com/controllers),
[modules](https://docs.nestjs.com/modules), [dynamic modules](https://docs.nestjs.com/fundamentals/dynamic-modules),
[pipes](https://docs.nestjs.com/pipes), [custom providers](https://docs.nestjs.com/fundamentals/custom-providers)
(`@Optional()`), [circular dependency](https://docs.nestjs.com/fundamentals/circular-dependency) (`forwardRef`),
[events](https://docs.nestjs.com/techniques/events).

## What the polish changed

| Before (ts-nest) | Now | Why |
|---|---|---|
| `inside: [ServerBody, LocationBody]` on 5 directives; an `extends: [NodeBody]` option | both gone. A scope class **extends** another as a plain TS class and holds its directives (`LocationBody extends RouteBody`); a plugin joins the shared one (`@Scope(RouteBody)`) | two options fewer; plain TS |
| `@Value` for every value; optional meant "has a default", so `to: string = ""` then `to \|\| undefined` | `@Value` = must be written; `@Optional` = may be left out (`= default`, or `?` for undefined) | judge's fixes 1 and 3: `@Value ... ms?: number` and `@Optional` on a required value both fail to compile |
| p4 named the first bad node-type member | one error names all | judge's fix 2 |
| `type: "Compose"` repeating the method name; fps and connect read in 4 places | `type.name` is the written word; rasl exports `nodeSpec(head, block)` | each written once |
| esbuild: NOT RUN | run: esbuild emits no parameter types; the app built with it **stops at startup** with a DeclarationError | no silent misread |
| TS 7: NOT CHECKED | tsgo 7.0.0-dev.20260707.2: good code exit 0, metadata emitted, app runs, same planted error counts | |

App output matches the winner's run (diffed) but for one "known:" list's order.

## Concepts: 11 (9 are Nest's own)

`@Module` (+`register()`) · scope class (`@Scope(name)` defines, `extends` shares, `@Scope(Other)` joins) ·
directive method (`many`/`inherit`/`restart`) · value parameter (`@Value`/`@Optional`/`@Key`) · pipe ·
flags class · `@Body` (`Block.get/all/entries(Class, "name")`, or `Lines`; `forwardRef` in a cycle) ·
`ConfigError` · program (`VillanelleFactory.create`, `load`, `apply`, `@OnChange`, `ChangeFailed`,
`Loader`). New to Nest users: value types (`@ValueType` + static `parse`; `choice()`) and select scopes
(`abstract class NodeType extends Chosen<NodeHead, NodeSpec>`, `type.build(head)`, `type.name`, `@Head()`).

## Where Nest has no idiom (extended in its spirit)

Name = method name; values positional; many = rest; `choice()` (Nest states an enum twice);
select scope = abstract-class token; `many`/`inherit`/`restart`; `@Optional` carries Nest's provider
marker over to values; `@OnChange` after `@OnEvent`, `ChangeFailed` = deliberate, any other error = bug;
include = `IncludeModule.register({ maxDepth: 16 })`.

## Checks (`./run.sh`; `evidence/`)

tsc 6.0.3: good code exit 0 (with 17 type pins, `types.test.ts`). `node out/app.js` exit 0: rasl
(a v2 edit: restart, retune, stop, one `ChangeFailed`), a bad config (10 located; one a repeated `@Key` the winner let pass),
webby + webby-gzip. Planted, tsc exit 2 each:

| Planted | tsc |
|---|---|
| p1: `number[]` not rest · literal union · required `T \| undefined` · readonly rest · `@Value` on `ms?` · `@Optional` on a required value | ×6 |
| p2: `IntPipe` on a `string` | ×1 |
| p3: `get(GraphBody, "fsp")` · `Rate` as `number` · absent `target` unchecked | ×3 (4 errors) |
| p4: node type builds `string` · takes no head | ×1, naming both |
| p5: `Change<string>` for `node` · `root` of an unchecked load | ×2 |

**Startup** (run, all listed at once): interface value type, `import type` class, undecorated
parameter, undocumented flag, public helper method, unlisted scope, unlisted base scope class,
duplicate directive, missing provider; and (esbuild probe) no emitted parameter types.
**Only at load** (run): `get()` on a repeating directive (round 9 caught this at compile time: a
regression); **reading a directive a block can never hold**, and only when a config reaches that code.
**Nowhere:** two same-typed values swapped; a wrong scope of an imported package. A `@Key` on an
optional parameter is refused, but with the `@Optional` message.

## Open for the owner (choices, not requirements)

- **Wrong-block reads at startup** (his kept choice) are not met. ts-typed showed tsc can catch them
  with a `Block<C>` typed by the block's class; here that means writing the scope twice
  (`@Body(GraphBody) block: Block<typeof GraphBody>`), which a check could keep in step. It is the
  judge's one candidate graft; not taken without his yes.
- **`@OnChange` handlers vs his v6 pick `applied(failures)`**: failures here come from handlers via
  `app.apply()`. A revisable choice to put back to him.

## Costs

- Legacy decorators and a compile step: Node cannot strip them; parameter properties fail
  `--erasableSyntaxOnly` (run). esbuild (under tsx and vitest's default transform) drops the metadata
  (run): users' tests need tsc or swc (swc NOT RUN). Standard decorators cannot decorate parameters.
- Method names follow the config (`max_count`); helpers must be `#private`.
- `?` and `@Optional` say one thing twice; tsc keeps them in step.
- `forwardRef` where a shared scope opens a block of a class extending it.
- A shared scope (`route`, `timing`) needs a name and doc, though never written as a block.
- Errors read "Unable to resolve signature of parameter decorator", reason last; ~100 lines of type checks.
- Runtime: a ~1,100-line prototype (subset parser; minimal `set`/`snippet`/`use`/include).

**NOT RUN:** swc; vitest and tsx themselves (only esbuild); editor hovers; TS other than 6.0.3 and the
tsgo preview; Nest docs re-read.
