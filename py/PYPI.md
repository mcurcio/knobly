# knobly

A small, friendly configuration language, read by Python, TypeScript and C++ parsers built from one grammar.

knobly files look like nginx's: directives ended by `;`, blocks in `{ }`, `#` comments. On top of that they have
variables, reusable snippets and included files, so a big config doesn't have to repeat itself.

```bash
pip install knobly
```

Python 3.11 or later. The only dependency is the ANTLR runtime.

## A first program

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
port = server.directives("port")[0].values[0].integer()  # 8080
debug = server.directives("debug")[0].values[0].boolean()  # False
print(len(tree.diagnostics))  # 0 problems
```

## What you get

- **Easy to read and write.** Directives with values: words, `"strings"`, `'raw strings'`, `[lists]` and slices
  like `channel[1~3]`. A line break is just a space, so long lines wrap freely.
- **Keeps big configs DRY.** `@set` variables, `@snippet` / `@use` for repeated blocks, and `@include` for
  splitting a config across files, each include with its own variables.
- **Every value knows where it came from.** Problems arrive as diagnostics with a file, line and column, and a
  caret under the exact text. A bad file never raises; it tells you what is wrong.
- **Programs can edit configs, too.** Load a file, change a value or a variable, and save it back with every
  comment and the layout kept.
- **Typed.** The package ships its type annotations (`py.typed`).

## Learn more

- [User guide](https://mcurcio.github.io/knobly/), with every example in Python, TypeScript and C++
- [Language reference](https://mcurcio.github.io/knobly/language/)
- [Source, issues and releases](https://github.com/mcurcio/knobly)

MIT licensed.
