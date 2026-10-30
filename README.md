<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/site/pages/assets/logo-dark.svg">
    <img alt="knobly" src="docs/site/pages/assets/logo.svg" width="440">
  </picture>
</p>

<p align="center">
  <b>A small, friendly configuration language, with parsers for TypeScript, Python and C++ built from one grammar.</b>
</p>

<p align="center">
  <a href="https://github.com/mcurcio/knobly/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/mcurcio/knobly/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://mcurcio.github.io/knobly/"><img alt="User guide" src="https://img.shields.io/badge/docs-user%20guide-ff8a3d"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-3b3660"></a>
</p>

---

knobly files look like nginx's: directives ended by `;`, blocks in `{ }`, `#` comments. On top of that they have
variables, reusable snippets and included files, so a big config doesn't have to repeat itself:

```conf
# main.conf
@set $pixels 2284;
@set $leds_host "10.0.60.30";

graph {
    node Waveform hue_ramp {
        shape sine;
        frequency_hz 0.01;
    }

    @include "sink.conf" {        # one file, included twice,
        @set $name leds;          # each time with its own variables
        @set $host $leds_host;
    }

    @include "sink.conf" {
        @set $name porch;
        @set $host "10.0.60.31";
    }
}
```

(Excerpt of [`fixtures/rasl/split/main.conf`](fixtures/rasl/split/main.conf), a real config the tests load.)

## Why knobly

- **Easy to read and write.** A file is directives with values: words, `"strings"`, `'raw strings'`,
  `[lists]` and slices like `channel[1~3]`. A line break is just a space, so long lines wrap freely.
- **Keeps big configs DRY.** `@set` variables, `@snippet` / `@use` for repeated blocks, and `@include` for
  splitting a config across files, each include with its own variables.
- **Every value knows where it came from.** Problems arrive as diagnostics with a file, line and column, and a
  caret under the exact text. A bad file never throws; it tells you what is wrong.
- **Programs can edit configs, too.** Load a file, change a value or a variable, and save it back with every
  comment and the layout kept.
- **The same everywhere.** The TypeScript, Python and C++ parsers are generated from
  [one grammar](grammar/Knobly.g4) that is machine-checked to be unambiguous, and all three pass the same
  conformance tests. A file means the same thing in every language.
- **Light.** TypeScript and Python need only the ANTLR runtime; C++ is a single header with no dependencies.

## Quickstart

Take a config file, `app.conf`:

```conf
@set $port 8080;

server {
    host "127.0.0.1";
    port $port;
    debug false;
}
```

Load it, render it (which fills in variables, snippets and includes), and read typed values:

```python
from knobly import rendered, written
from knobly.files import file_source

config = written.Processor(source=file_source())
tree = rendered.render(config.load("app.conf"))

server = tree.block.directives("server")[0].block
port = server.directives("port")[0].values[0].integer()   # 8080
debug = server.directives("debug")[0].values[0].boolean()  # False
print(len(tree.diagnostics))                               # 0 problems
```

<details>
<summary>The same in TypeScript</summary>

```ts
import { knobly } from "knobly/written";
import { render } from "knobly/rendered";
import { fileSource } from "knobly/node";

const config = knobly({ source: fileSource() });
const tree = render(await config.load("app.conf"));

const server = tree.block.directives("server")[0]?.block;
const port = server?.directives("port")[0]?.values[0]?.integer();   // 8080
const debug = server?.directives("debug")[0]?.values[0]?.boolean(); // false
console.log(tree.diagnostics.length);                               // 0 problems
```

</details>

<details>
<summary>The same in C++</summary>

```cpp
#include <knobly/files.hpp>
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

namespace vw = knobly::written;
namespace vr = knobly::rendered;

const vw::processor config({.source = knobly::files::file_source()});
const vr::rendered tree = vr::render(config.load("app.conf"));

const vr::rendered_block server = tree.block().directives("server").at(0).block().value();
const auto port = server.directives("port").at(0).values().at(0).integer();    // 8080
const auto debug = server.directives("debug").at(0).values().at(0).boolean();  // false
```

</details>

These are shortened from the user guide's quickstart sample
([Python](py/examples/quickstart.py), [TypeScript](ts/examples/quickstart.ts), [C++](cpp/examples/quickstart.cpp)),
which every build runs.

## Install

knobly has not made its first release yet, so for now you build it from a clone:

```bash
git clone https://github.com/mcurcio/knobly
```

The [Quickstart page of the user guide](https://mcurcio.github.io/knobly/#get-it) has the exact steps for each
language. In short: TypeScript needs Node 24 and Java 11+ (to generate the parser), Python needs Python 3.11+ and
Java 11+, and C++ needs a C++20 compiler (and Python with `uv` to generate the headers). Once releases start, each
one on the [releases page](https://github.com/mcurcio/knobly/releases) will carry an npm tarball, a Python wheel,
and a single C++ header; nothing is published to npm or PyPI.

## Learn more

The **[user guide](https://mcurcio.github.io/knobly/)** shows every example in all three languages, with a tab per
language.

| If you want to... | Read |
|---|---|
| install knobly and run a first program | [Quickstart](https://mcurcio.github.io/knobly/) |
| load files, read values, pass overrides, handle problems | [Getting started](https://mcurcio.github.io/knobly/getting-started/) |
| learn everything a knobly file may say | [Language reference](https://mcurcio.github.io/knobly/language/) |
| change a config from a program and save it back | [Editing and saving](https://mcurcio.github.io/knobly/editing/) |
| use variables, snippets and included files | [Variables, snippets and includes](https://mcurcio.github.io/knobly/variables/) |
| report your own problems in a user's config | [Diagnostics and your own checks](https://mcurcio.github.io/knobly/diagnostics/) |
| see how the three languages' APIs differ | [How the bindings differ](https://mcurcio.github.io/knobly/differences/) |
| look up a language's full API | [TypeScript](ts/README.md), [Python](py/README.md), [C++](cpp/README.md) |

### The API at a glance

A program can work at three layers, each built on the one below:

- **The rendered tree** (`render`): variables, snippets and includes worked out into the directives a program
  reads. This is where most programs live.
- **The files as written** (`load`): the root file and every file it includes, with their variables. Edit them
  and save them back, comments and layout kept.
- **The syntax tree** (`parse`): one text as tokens and a tree, every character in exactly one token.

Each layer is its own import:

<!-- generated: members: entry points (tools/gen-api.py docs) -->
| Entry point | TypeScript | Python | C++ |
|---|---|---|---|
| what every layer shares, and the ports | `knobly`: `quote`, `text`, `ConfigText`, `memorySource`, `memoryWriter`, `Diagnostics`, `KnoblyError`, `DocumentSource`, `Place`, ... | `knobly`: `quote`, `text`, `ConfigText`, `memory_source`, `memory_writer`, `Diagnostics`, `KnoblyError`, `DocumentSource`, `Place`, ... | `knobly`: `quote`, `text`, `config_text`, `memory_source`, `memory_writer`, `diagnostics`, `knobly_error`, `document_source`, `place`, ... |
| the syntax tree | `knobly/syntax`: `parse`, `spanOf`, `textOf`, `Syntax`, `Token`, `Node`, `TokenKind`, ... | `knobly.syntax`: `parse`, `span_of`, `text_of`, `Syntax`, `Token`, `Node`, `TokenKind`, ... | `knobly::syntax`: `parse`, `span_of`, `text_of`, `syntax`, `token`, `node`, `token_kind`, ... |
| the low level | `knobly/written`: `knobly`, `formatDiagnostic`, `DocumentGraph`, `Statement`, `StatementKind`, ... | `knobly.written`: `Processor`, `format_diagnostic`, `DocumentGraph`, `Statement`, `StatementKind`, ... | `knobly::written`: `processor`, `format_diagnostic`, `document_graph`, `statement`, `statement_kind`, ... |
| the rendered tree | `knobly/rendered`: `render`, `Rendered`, `Directive`, `KeyRule`, ... | `knobly.rendered`: `render`, `Rendered`, `Directive`, `KeyRule`, ... | `knobly::rendered`: `render`, `rendered`, `directive`, `key_rule`, ... |
| the include extension | `knobly/include`: `include`, ... | `knobly.include`: `include`, ... | `knobly::extensions`: `include`, ... |
| files on disk | `knobly/node`: `fileSource`, `fileWriter`, ... | `knobly.files`: `file_source`, `file_writer`, ... | `knobly::files`: `file_source`, `file_writer`, ... |
| files over `fetch` | `knobly/browser`: `fetchSource`, `fetchWriter`, ... | none | none |
<!-- end generated -->

## Project status

knobly is young and has not made its first release yet; its API may still change. The TypeScript, Python and C++
bindings are complete for all three layers and pass the same conformance tests. A higher-level API, where a program
declares the directives it expects, is planned. knobly began as the config format of
[rasl](https://github.com/mcurcio/rasl), which will use it.

## Contributing

Bug reports, ideas and pull requests are welcome: open an
[issue](https://github.com/mcurcio/knobly/issues) to start. [CONTRIBUTING.md](CONTRIBUTING.md) explains how the
repository fits together and how to build and test it. AI coding agents start at [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE) © 2026 Matt Curcio
