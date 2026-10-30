# C++ for knobly, header-only: what you would get

You picked option A on 2026-10-29: the C++ version ships as **header files only** (files a C++ program includes and
compiles itself, so there is no compiled library to build, install or link) and does not use the ANTLR runtime. This
page shows what that looks like. The full design is `design/cpp-header-only.md`.

## 1. One program in three languages: load, read a value, change it, save

```cpp
// C++
vw::document_graph graph = vw::processor({.source = vl::files::file_source()}).load("main.conf");   // load
std::cout << vr::render(graph).block().directives("port").at(0).values().at(0).integer();          // read
for (vw::written_directive d : graph.root().block().directives("port")) d.set(vl::text("9090"));    // change
graph.save(vl::files::file_writer());                                                               // save
```

```ts
// TypeScript
const graph = await knobly({ source: fileSource() }).load("main.conf");
console.log(render(graph).block.directives("port")[0]?.values[0]?.integer());
for (const d of graph.root.block.directives("port")) d.set(text("9090"));
await graph.save(fileWriter());
```

```python
# Python
graph = Processor(source=file_source()).load("main.conf")
print(render(graph).block.directives("port")[0].values[0].integer())
for d in graph.root.block.directives("port"): d.set(text("9090"))
graph.save(file_writer())
```

The C++ lines leave out the `#include` lines and three short names: `vl`, `vw` and `vr` stand for `knobly`, its
low level (`written`) and its rendered tree (`rendered`). The names are the same words in each language, in each
language's usual spelling.

## 2. What you asked for

- 2026-10-29: header-only, no ANTLR runtime, "but with as much auto codegen as possible to unify with typescript and
  python".
- 2026-10-28: "clean, easy to comprehend API design", "idiomatic in each language", "consistent across layers",
  codegen "so we dont have to maintain n languages by hand".
- 2026-10-25: "I don't want villanelle dependent on third party libraries (including pydantic) so any shims must be
  optional extensions rather than core." The C++ version depends on nothing but the C++ standard library.
- 2026-10-23: "Don't commit the generated code, just the source."

## 3. The shape

**Can the parser be generated without ANTLR? Yes, shown.** A small generator of our own (Python, no packages) reads
the grammar file `grammar/Knobly.g4` and writes the C++ code that splits a text into tokens and builds the tree.
A 653-line prototype did this, and the result gave the expected answer, byte for byte, on all 168 syntax test cases
the TypeScript and Python versions pass, with C++ exceptions turned off. The grammar is simple enough for this: no
special cases a generator would need help with. What stays hand-written is policy the spec states in words: which
error code a mistake gets, and how far the parser skips after a broken statement before reading on.

**Files.** One folder of headers, one per layer, as now: `knobly.hpp` (shared), `syntax.hpp`, `written.hpp`,
`rendered.hpp`, `files.hpp`, `extensions.hpp`. The generated ones are made during the build from a git checkout, which
needs only Python; each release also carries them ready-made, plus the whole library as one file.

| Part | C++ | TypeScript today | Python today |
|---|---|---|---|
| parser, generated | about 600 lines, from our generator | 1,940, from ANTLR | 1,696, from ANTLR |
| parser library needed at run time | none | ANTLR | ANTLR |
| parser code by hand (error codes, skipping) | about 300 | 637 | 618 |
| declarations of every public name, generated from the shared API file | 3,000 to 4,000 (estimate) | 1,762 | 3,259 |
| everything else by hand (all layers) | 8,800 to 12,300 (estimate) | 5,114 | 5,805 |
| test adapter (answers the shared test driver) | about 800 | 285 | 428 |
| tools written once, in Python | parser generator 800 to 1,000; declarations generator 1,100 to 1,400 | declarations generator 632 | declarations generator 978 |

C++ needs more hand code because it does not free unused memory by itself: every object knobly hands out must
keep track of its own lifetime.

## 4. Two questions

**Q1. When something goes wrong that a program should expect (a file it cannot read, a value that is not a number),
should C++ throw an exception or return the error as a value?**

| Option | Cost |
|---|---|
| **A. Throw an exception, as TypeScript and Python do** (recommended) | programs built with exceptions switched off (common in games and small devices) still compile, but such an error stops them; adding a returned-value form later would be a second API |
| B. Return the value or the error, and the program checks each call | every call needs a check; C++ reads unlike the other two; the spec's open proposal for languages that work this way would need accepting first |

**Q2. When a program throws away a loaded config, what happens to the handles (references to a line or a value) it
still holds?**

| Option | Cost |
|---|---|
| **A. They keep the config alive until the last one goes** (recommended) | a little bookkeeping on every copy; removed lines stay in memory until the config goes; two library list types instead of the standard one. In exchange, a handle can never point at freed memory |
| B. They borrow it: valid only while the config lives | fastest, but using a handle after the config is gone crashes or reads garbage, and no compiler reliably warns |

**Recommended defaults you can reopen:** C++20 (the 2020 language version); header-only by default, with an optional
switch that compiles knobly once in one of the program's files to save compile time; the one-file copy as an
extra release download; nothing to link and no download during the build; positions counted in bytes; names spelled
like the C++ standard library (`replace_with_text`); a version tag inside every name so two knobly versions in one
program cannot mix; no web-fetch adapters; no custom memory allocator.

## 5. Costs and what is deferred

- We keep a parser generator of our own. If the grammar ever needs something it cannot handle, it must grow first;
  ANTLR would have just worked.
- TypeScript and Python stay on ANTLR for now, so two parser technologies are held together by the shared tests.
  Comparing them on 20,000 random texts found two cases where the TypeScript and Python parsers break the spec's own
  rule (a broken line can swallow the good lines after it; two broken lines can merge into one). The C++ parser
  follows the spec; the other two need fixing, with new test cases.
- Header-only means every file that includes knobly compiles its code; the compile-once switch is the remedy.
  The syntax layer added 0.07 seconds to one file's compile; the larger layers are not measured yet.
- Deferred: C++ modules (a newer way to package C++ code, not yet solid in every compiler); a returned-value API if
  Q1 picks A; using the same generator for TypeScript and Python (it would drop their ANTLR dependency; offered as
  a separate idea, not planned).

## 6. Milestones

| Step | What lands | Rough size (hand-written lines) |
|---|---|---|
| 1. Tracer | the parser generator, the C++ declarations generator, parsing, the test adapter: all 168 syntax tests pass | generators 1,500 to 1,900; C++ 1,800 to 2,300; adapter 800 |
| 2. Low level | load, edits, save | 5,000 to 7,000 |
| 3. Rendered tree | render, walk, addresses, diff: all 380 shared tests pass | 2,000 to 3,000 |
| 4. Packaging | test runs on four compilers, install, release files | 400 to 800 |
