# Milestone 7, frozen for the binding lanes (beads vil-umh.16, vil-umh.17, vil-umh.18)

This page is what the TypeScript lane (`ts/`) and the Python lane (`py/`) build in milestone 7. It is frozen: a lane
that finds it wrong appends the finding to `.claude/errata.md` and does not diverge silently. The rules live in
`spec/` (canonical); where this page and `spec/` differ, `spec/` wins and the difference is an erratum.

## What this rests on

The owner's words, quoted, not widened:

- His first ask (2026-10-28): "clean, easy to comprehend API design", "idiomatic in each language", "consistent
  across layers", and codegen "so we dont have to maintain n languages by hand".
- Q3 on the round 15 review page (2026-10-29), picked A: the schema is the source of every public signature.
- He merged PR 5 (2026-10-30) after these three leftovers were reported with a recommendation to do them in a
  follow-up PR. Each item below is that recommendation (beads vil-umh.16 to .18); the choices inside them are design
  calls, revisable.

Not in this milestone: vil-umh.15 (may `:` start a word; the grammar is unchanged), the high level, and any public
rename beyond what an item needs (none is needed: "Behaviour changes" lists every visible change).

## 1. What landed outside `ts/src` and `py/src` (this lane, done)

| Path | Change |
|---|---|
| `spec/schema/api.json` | No language anywhere: the error groups' `ts` / `py` bases, the factories' per-language forms, the free functions' per-language `module` objects, the argument type error's two sentences and every `languages` list are gone. `module` is now what the adapter module holds (`files`, `fetch`, `include`); `factory` is `{"of": concept}`. Every `note` is split into `doc` (emitted) and `rationale` (never emitted) |
| `spec/schema/api.schema.json` | `languages` and `languageBase` gone; `doc`, `rationale` and `moduleName` (`files`, `fetch`, `include`) added; the `factory`, `module` and `argument type error message` shapes lose their language keys |
| `spec/schema/diagnostics.json` | three meanings lose "(milestone 5)" |
| `tools/api/loader.py` | `Language` holds every language fact (`error_roots`, `argument_type_message`, `modules`, `factory_forms`, `omit`, and `name`); the loader fills each group's base, each factory's form and each concept's and kind list's bindings from them, and checks them (a root without a class, a class for a non-root, an unknown module or factory, a left-out concept still used); the doc check; 6 new planted breakages (27 in all) |
| `tools/api/emit_ts.py` | its `LANGUAGE` states TypeScript's facts; emits `doc` |
| `tools/api/emit_py.py` | its `LANGUAGE` states Python's facts; item A (section A below); emits `doc`; wraps a too-long return annotation as ruff does |
| `tools/api/stub.py` (new) | a third binding in miniature, loaded by `--check` |
| `tools/api/validate.py` | 3 new planted breakages (a per-language error base, a language list, a `note`) |
| `tools/gen-api.py` | Python's third output, `py/tests/api_contract.py`; the stub check; the old meta-schema base check goes (no bases in the schema) |
| `py/.gitignore` (build wiring) | ignores the generated `tests/api_contract.py` |
| `spec/codegen.md` | status; section 1 (stub); section 3 (no per-language data; "Docs and rationale"); section 4 (Python's public types; the module table); section 10 rewritten; section 11 costs |
| `spec/spec.md` | the argument type sentence's home; regenerated tables (2.4, 2.5) |
| `spec/binding-guide.md` (section 5), `README.md`, `.claude/skills/villanelle-binding/SKILL.md` | a new binding's facts go in its emitter; the generated `api_contract.py` |

`bash tools/check.sh` passes: "27 planted breakages caught; ts and py rendered; a third binding's stub rendered 114
names with no schema edit; docs tables current", and the meta-schema check catches 8.

## 2. Per item

### A. Python's public types and generated types are one (vil-umh.16)

**Mechanism.** Every annotation in generated Python that names a concept the binding implements by hand (a
`Protocol` concept, or a union over them) names the binding's public class, imported for the type checker only:

```python
if TYPE_CHECKING:
    import villanelle
    import villanelle.rendered
    import villanelle.written

class Directive(Protocol):
    @property
    def parent(self) -> villanelle.rendered.Directive | None: ...
    @property
    def written(self) -> villanelle.written.WrittenDirective: ...

KeyRule: TypeAlias = Callable[["villanelle.rendered.Directive"], "str | None"]

class DiagnosticError(VillanelleError):
    diagnostic: villanelle.LocatedDiagnostic
```

A concept the generator writes whole (a plain record, a named type, a callback, a union of records: `Change`) is
named by its generated class, which the binding already re-exports as the public one. Where a name is evaluated when
the module runs (a base class, a callback alias's parameters) it stays the generated class or a string. Prior art:
annotating with a package's concrete public classes, cycles broken with `TYPE_CHECKING` imports (PEP 484, PEP 563),
as typeshed and `lsprotocol` do; making the Protocols public was rejected (two public types per concept; `match` and
`isinstance` need the classes).

**Generated output, Python.**

| Before | Now |
|---|---|
| record fields, Protocol members, error fields and `KeyRule` typed with `_api` Protocols (`LocatedDiagnostic`, `Directive`) | typed with the public classes (`villanelle.LocatedDiagnostic`, `villanelle.rendered.Directive`) |
| `_api.written.Statement`, `WrittenValue`, `Variable`, `ExpandedValue` (unions over Protocols) | gone: the binding's own unions are the only ones; `api_contract.UNIONS` lists each public union's variant classes |
| `_api/names.py` (`PUBLIC_NAMES`, `ERROR_GROUP_OF_CLASS`, `MATCH_ARGS`) | gone: `PUBLIC_NAMES` and `MATCH_ARGS` in `py/tests/api_contract.py`, `ERROR_GROUP_OF_CLASS` in `py/conformance/shapes.py` |
| `<Module>Functions` and `<Class>Constructor` Protocols in `_api/<layer>.py` | in `py/tests/api_contract.py`, every type named through its public module |

**Generated output, TypeScript.** Unchanged (TypeScript's types already are the generated interfaces).

**The Python lane changes** (each from `mypy` and `pytest` on this commit; none is in generated code):

- `src/villanelle/written/_value.py`, `_model.py`, `rendered/_tree.py`: stop importing `Statement`, `WrittenValue`,
  `Variable`, `ExpandedValue` from `villanelle._api.written` (the package fails to import until then); use the
  binding's own unions. `_value.py:387`: narrow `origin.place` (`Place | Override`) before reading `.variable`.
- Return and parameter types that name `_api` Protocols where the generated signature now names the public class:
  `_report.py` (`LocatedDiagnostic.place` / `via` fields; `Diagnostics.__iter__`), `written/_model.py`
  (`DocumentGraph.diagnostics`, `UseLine.snippets`), `written/_document.py` and `_graph.py` (the
  `BadTextError(...)` arguments: public `Diagnostic`), `written/_expand.py` (`Expansion(diagnostics=...)`),
  `rendered/_tree.py` (`Directive.written`), `rendered/_render.py` (`Rendered.diagnostics`, `graph`, `addresses`).
- `conformance/adapter.py`: no `villanelle._api` import: annotate with the public classes (`rendered.Directive`,
  `written.Statement`, `villanelle.Place`, ...), import `ERROR_GROUP_OF_CLASS` from `shapes`; fix its docstring.
- `tests/test_api_names.py`: import `PUBLIC_NAMES`, `MATCH_ARGS`, `UNIONS` and the `<Module>Functions` /
  `<Class>Constructor` Protocols from `api_contract`; compare each public union with `UNIONS[name]` instead of a
  generated alias. `tests/test_readers.py`, `test_load.py`, `test_tracer.py`: the public types in place of
  `villanelle._api.shared` / `written`.
- The milestone 6 workarounds go: `Rendered.addresses` / `diff` taking a function of either `Directive`, and the
  helpers annotated with `_api` types (errata, milestone 6 Python lane).
- Done when `grep -rn "villanelle._api" py/tests py/conformance docs` is empty and the four Python gates pass.

### B. No language in the schema (vil-umh.17)

Every fact about one language moved from `api.json` into that emitter's `LANGUAGE` (spec/codegen.md section 10):

| Fact | Was (`api.json`) | Now (`tools/api/emit_<lang>.py`, `LANGUAGE`) |
|---|---|---|
| root error groups' classes | `"ts": {"base": "Error"}` on five groups | `error_roots` |
| factory forms | `"factory": {"of": "processor", "ts": "package function", "py": "constructor"}` | `factory_forms` (TypeScript: the processor is `package function`; default `constructor`) |
| adapter modules | `"module": {"ts": "node", "py": "files"}` | `modules`: TypeScript `files` → `node`, `fetch` → `browser`, `include` → `include`; Python `files` → `files`, `include` → `include` |
| argument type sentence | `"ts": "...", "py": "..."` | `argument_type_message` |
| exists in some bindings only | `"languages": ["ts"]` on four options records, `platform fetch`, `walk control` | Python's `omit` (options records, `walk control`); the `fetch` module's concepts are gone wherever the module is not mapped |

The proof is `tools/api/stub.py`: a made-up third language (its own error classes, one adapter module) that
`tools/gen-api.py --check` loads beside the real two and renders as a names list, with no schema edit. Prior art:
`protoc` plugins and Smithy code generators keep target-language facts in the generator, never in the model.

**Generated output.** Identical in both languages (same classes, bases, factories, modules, sentences, public
names); only doc comments changed (item C). **Each binding deletes or changes:** nothing.

### C. Docs and rationale (vil-umh.18), and `Diagnostics.toArray()`

Each schema entry has `doc` (emitted as JSDoc and docstrings) and `rationale` (never emitted). About 35 notes were
split: history (`milestone N`, "was ..."), owner quotes, bead ids and one-language advice ("TypeScript checks ...",
"a tuple in Python") moved to `rationale`. The loader refuses a bead id, `milestone N`, an `owner, <date>` quote or
a language's name in every emitted text (each `doc`, a group's `raised when`, a constant's `means`, a code's
`meaning`), planted three ways. Prior art: Smithy's `@documentation` trait beside comments that never reach
generated code.

**Generated output.** Both languages: doc comments only (for example `render`'s doc no longer quotes the owner,
`ConfigText`'s no longer cites vil-umh.6, `collect` now says what it does, `ProgramCode`'s no longer explains
TypeScript and Python). Every generated file's header drops its owner quote.

**`Diagnostics.toArray()`: dropped** (design call). It is in no schema or spec; the iterate trait already gives
`[...diagnostics]` and `Array.from(diagnostics)`, and adding it to the schema would give Python a `to_array()`
where `list(diagnostics)` is the idiom. **The TypeScript lane** deletes `toArray()` from `ts/src/report.ts` and
changes its one use, `ts/src/rendered/report.test.ts`, to `[...sink]`.

## 3. Behaviour changes

- TypeScript `Diagnostics.toArray()` is removed (use `[...diagnostics]`).
- Python, type checking only (no run-time change): generated records, error fields, `KeyRule`, Protocol members and
  the `<Module>Functions` / `<Class>Constructor` Protocols are typed with the public classes. A program annotating
  with public classes now type-checks where it needed narrowing (`def key(d: rendered.Directive)` is a
  `rendered.KeyRule`); a program that annotated with `villanelle._api` Protocols still type-checks where it only
  reads (a public class satisfies its Protocol), but `_api` is private and its names may go.
- Python: `villanelle._api.written.Statement`, `WrittenValue`, `Variable`, `ExpandedValue` and `villanelle._api.names`
  no longer exist (private; the public unions are unchanged), and the `<Module>Functions` / `<Class>Constructor`
  Protocols left `villanelle._api` for `py/tests/api_contract.py`.
- Python: `typing.get_type_hints()` on a generated class resolves only once the public module it names is imported
  (it is whenever `villanelle` is).
- Doc comments of the generated declarations changed in both languages (item C); spec 2.4's and 2.5's generated
  text lost its milestone clauses.
- No public name, import path, signature, error class or message changed.

## 4. Costs, and what this leaves

- Python checks are red at this commit until the Python lane lands section A's list (errata, milestone 7).
- A language's facts are Python data in its emitter; the spec 2.8 and contract 4.2 tables still show them.
- The doc check is lexical: it catches `vil-`, `milestone N`, `owner, <date>` and language names, not every kind of
  history ("was statement") or advice; review still reads `doc`.
- `py/tests/` now holds one generated file beside hand-written tests (git-ignored, regenerated by `conftest.py`'s
  `tools/gen.sh py` run).
