# Round 10, Python: a directive is a dataclass

The owner said on 2026-10-28: "They are trying to combine the inspirations rather than choosing one
model". This Python binding uses one model only: Python's own `dataclasses`. A directive is a class
under `@vl.directive`, which makes it a frozen dataclass. **Its fields are what gets written.**
Fields before `_: KW_ONLY` are the values, in the order they are written. Fields after it are
written by name:
- a `bool` is a flag word on the line;
- a field typed with a directive is a line in the block, and a tuple of them may repeat;
- a tuple of plain records is a block of plain data lines.

A value's rules (doc, bounds, key) sit on its field through `vl.field(...)`, the way
`dataclasses.field` works. The record built from a line is what the program reads.

Every code block below is copied from a checked file under `round10/final-py/`. pyright 1.1.407
strict and mypy 1.18.2 --strict both exit 0 on it (`evidence/good.txt`). "Excerpt" marks a block
with lines left out; the left-out lines are named.

---

## 1. A web server's directives (`webby/__init__.py`, excerpt: `Duration`, `Proxy`, `Timeout`, `Header` and `pkg` left out)

The config these serve, written out from the lines `prove_runtime.py` builds (typed by hand, not
copied from a file):

```nginx
server example {
    listen 8080 443 tls http2;
    root /var/www;
    gzip true;                         # webby-gzip's directive, §3
    location /api {
        proxy http://10.0.0.5:8080;
        header Access-Control-Allow-Origin *;
        location /api/v2 { timeout 30s; }
    }
    types { text/html html htm; application/json json; }
}
```

```python
@vl.directive()
class Listen:
    """Ports, then modes: listen 8080 443 tls http2. May repeat."""

    ports: tuple[int, ...] = vl.field(min=1, max=65535)
    _: KW_ONLY
    tls: bool = False
    http2: bool = False


@vl.directive(inherit=True)
class Root:
    """Serve files from here. Inner locations read the nearest one."""

    path: str = "/var/www/html"
```

```python
@vl.directive()
class Location:
    """Serve a path prefix. Locations nest."""

    path: str = vl.field(key=True)
    _: KW_ONLY
    root: Root  # inherits: written here, else the nearest block's, else Root's default
    proxy: Proxy | None = None
    timeout: Timeout | None  # inherits; None when no block writes it
    headers: tuple[Header, ...] = ()
    children: tuple[Location, ...] = ()

    def __post_init__(self) -> None:
        if not self.path.startswith("/"):
            raise vl.ConfigError("a location path starts with /", at="path", code="webby/relative-path")
```

```python
@dataclass(frozen=True)
class MimeLine:
    """One `types` line: a MIME type, then the extensions that map to it."""

    mime: str
    extensions: tuple[vl.Word, ...]


@vl.directive()
class Types:
    """A MIME type, then the extensions that map to it: types { text/html html htm; }."""

    _: KW_ONLY
    lines: tuple[MimeLine, ...] = ()  # a tuple of plain records: the block is lines of data

    @property
    def by_extension(self) -> Mapping[str, str]:
        return {ext: line.mime for line in self.lines for ext in line.extensions}


@vl.directive()
class Server:
    """One virtual server: server example { ... }."""

    name: vl.Word = vl.field(key=True)
    _: KW_ONLY
    listen: tuple[Listen, ...] = ()
    root: Root  # inherits: written here, else Root's own /var/www/html
    types: Types = Types()
    locations: tuple[Location, ...] = ()


@vl.file
class WebbyFile:
    """A webby config: its servers."""

    servers: tuple[Server, ...] = ()
```

How to read these:
- `listen 8080 443 tls http2`: the numbers fill `ports` (each one checked to be from 1 to 65535),
  and `tls` and `http2` are flag words.
- `Root` is declared `inherit=True`, so a holder writes `root: Root` with no default. A location
  that does not write `root` reads the nearest one written around it, else `Root`'s own
  `/var/www/html`. The default is stated once, in `Root`.
- `Types` holds a tuple of `MimeLine`, a plain dataclass, so its block is lines of data, not
  directives.
- A location's `__post_init__` raises `vl.ConfigError(at="path")`. That rejects
  `location api` with an error placed at that line.

## 2. A nested, repeated directive: rasl's `group` (`rasl/__init__.py`, excerpt: value types, `ui` and the shipped node types left out)

The config, from briefing-v9 §1 (unchanged since v8):

```nginx
graph {
    fps 30;                           # every block below reads 30 unless it writes its own
    include "palettes.conf";          # first-party plugin: read once, checked where it lands

    node Waveform hue_ramp {          # `Waveform` comes from a third-party package
        shape sine;
        frequency_hz 0.01;
    }
    node Compose hsl {
        ports { hue; saturation; lightness; }   # this block is read by `ports` itself
        connect hue_ramp hue;
    }

    group fireplace {                 # a group holds what a graph holds ...
        fps 20hz;
        group mantel {                # ... including another group
            node TwinkleEffect twinkle { use twinkle hsl; }
            node DdpSink leds {
                target $host;
                max_count $pixels;
                connect twinkle[0:144] pixels;
            }
        }
    }
}
```

```python
@vl.directive(inherit=True)
class Fps:
    """Frames per second. A block that does not write it reads the nearest one written, else 30."""

    rate: Rate = Rate(30)


@vl.directive()
class Connect:
    """Feed this node from another's output: connect twinkle[0:144] pixels."""

    source: Endpoint
    to: str | None = None


class NodeKind(Protocol):
    """What every node type holds; `node <type> <id>` picks a directive declared select=NodeKind."""

    @property
    def fps(self) -> Fps: ...
    @property
    def inputs(self) -> tuple[Connect, ...]: ...


@vl.directive()
class Node:
    """node <type> <id> { ... }: one node of the graph. The type opens the block."""

    kind: NodeKind
    id: vl.Word = vl.field(key=True, doc="Unique among its siblings.")


@vl.directive()
class Group:
    """A named group of nodes. Groups nest: a group holds what a graph holds."""

    id: vl.Word = vl.field(key=True, doc="Unique among its siblings.")
    _: KW_ONLY
    fps: Fps
    items: tuple[Node | Group, ...] = ()  # in written order


def _walk(items: tuple[Node | Group, ...]) -> list[Node]:
    out: list[Node] = []
    for item in items:
        out += _walk(item.items) if isinstance(item, Group) else [item]
    return out


@vl.directive()
class Graph:
    """The node graph."""

    _: KW_ONLY
    fps: Fps
    items: tuple[Node | Group, ...] = ()

    def nodes(self) -> list[Node]:
        """Every node, groups flattened, in written order."""
        return _walk(self.items)

    def __post_init__(self) -> None:  # a check across nodes, placed at the line that caused it
        ids = {n.id for n in self.nodes()}
        for n in self.nodes():
            for c in n.kind.inputs:
                if c.source.node not in ids:
                    raise vl.ConfigError(f"no node {c.source.node!r}", at=c, code="rasl/unknown-node")
```

- `group` repeats and nests because its holders' field is `items: tuple[Node | Group, ...]`.
  `Group` names itself in that field.
- `id` carries `vl.field(key=True)`. Two siblings with the same id are rejected at the second
  line (`vl/duplicate-key`). The same id inside another group is allowed.
- `fps: Fps` has no default. Each graph, group and node reads the nearest `fps` written around
  it, else `Fps`'s own 30. A holder that writes `fps: Fps = Fps(Rate(5))` is rejected when the
  program starts.
- `node Waveform hue_ramp`: `kind` is typed with the `Protocol` `NodeKind`, so the word after
  `node` names a directive declared `select=NodeKind`. That directive's fields then form the
  node's block.

A third party adds a node type (`rasl_waveform/__init__.py`, whole file):

```python
"""A third-party node type for rasl: `node Waveform hue_ramp { shape sine; }`.

`select=rasl.NodeKind` makes it a word `node` can pick; its fields hold rasl's `fps` and
`connect`. rasl never names this package; the program hands both to knobly.
"""

from __future__ import annotations

from dataclasses import KW_ONLY
from typing import Literal

import knobly as vl
import rasl

Wave = Literal["sine", "sawtooth", "square"]


@vl.directive(restart=True)
class Shape:
    """The wave's shape. Changing it restarts the node."""

    wave: Wave = "sine"


@vl.directive()
class FrequencyHz:
    """Cycles per second."""

    hz: float = vl.field(default=1.0, min=0, max=1000)


@vl.directive("Waveform", select=rasl.NodeKind)
class Waveform:
    """A periodic signal, one value per output channel."""

    _: KW_ONLY
    fps: rasl.Fps  # rasl's fps: here, else the nearest block, else 30
    inputs: tuple[rasl.Connect, ...] = ()
    shape: Shape = Shape()
    frequency_hz: FrequencyHz = FrequencyHz()


pkg = vl.Package("rasl-waveform", doc="Periodic signals for rasl.", directives=[Waveform, Shape, FrequencyHz])
```

## 3. The plugin: webby-gzip adds `gzip` to webby's blocks (`webby_gzip/__init__.py`, whole file)

```python
"""webby-gzip: adds `gzip` to webby's blocks, which it does not own. webby never names it.

`inside=` places a directive in another package's records; no webby field holds it, so this
module applies its own changes (nginx: each module reads its own conf).
"""

from __future__ import annotations

from collections.abc import Callable

import knobly as vl
import webby


@vl.directive(inside=[webby.Server, webby.Location], inherit=True)
class Gzip:
    """Compress responses: gzip true. Inner locations read the nearest one."""

    on: bool = False  # a value before KW_ONLY: written `gzip true`, not a flag word


@vl.directive(inside=[webby.Server, webby.Location], inherit=True)
class GzipTypes:
    """MIME types to compress: gzip_types text/html application/json."""

    types: tuple[vl.Word, ...]


def apply(changes: vl.Changes, turn_on: Callable[[vl.Place, bool], None]) -> list[vl.Failure]:
    """This module's side of a load: apply its own changes, return what failed."""
    failures: list[vl.Failure] = []
    for change in changes.of(Gzip):
        match change:
            case vl.Added(value=Gzip(on=on), place=at) | vl.Changed(value=Gzip(on=on), place=at):
                try:
                    turn_on(at, on)
                except OSError as e:
                    failures.append(vl.Failure(change, str(e)))
            case vl.Replaced(value=Gzip(on=on), place=at):
                turn_on(at, on)
            case vl.Removed(place=at):
                turn_on(at, False)
    return failures


pkg = vl.Package("webby-gzip", doc="Response compression for webby.", directives=[Gzip, GzipTypes])
```

webby never names this package. `inside=` places `gzip` in webby's `server` and `location`
blocks. No webby field holds it, so this module reads its own changes with `changes.of(Gzip)`.

## 4. The program side (`app.py`, excerpt: module docstring and imports left out)

```python
def read_file(path: str) -> str:
    """The I/O edge: the only code that touches the filesystem (core does no I/O)."""
    return Path(path).read_text()


# ── rasl ──

rasl_config = vl.Config(
    rasl.RaslFile,
    packages=[rasl.pkg, rasl_waveform.pkg],
    plugins=[include(max_depth=16)],
    loader=read_file,
)


def run_rasl(host: str, applied: vl.Applied | None) -> vl.Applied | None:
    """At start, and again each time the file changes (R27)."""
    match rasl_config.load("family_room.conf", variables={"host": host}, applied=applied):
        case vl.Rejected(diagnostics=diagnostics):
            for d in diagnostics:
                print(vl.format(d, read_file(d.place.path) if d.place else ""))
            return applied  # fail closed: keep running what runs
        case vl.Accepted(value=conf) as result:
            print("ui on", conf.ui.port.ports, "graph at", conf.graph.fps.rate)
            failures: list[vl.Failure] = []
            for change in result.changes.of(rasl.Node):
                match change:
                    case vl.Removed(previous=node):
                        print("stop", node.id)
                    case vl.Added(value=node) | vl.Changed(value=node) | vl.Replaced(value=node):
                        print("start or retune", node.id, node.kind.fps.rate)  # Replaced: a restart-marked edit
            return result.applied(handles=[rasl.Node, rasl.Ui], failures=failures)


# ── webby ──

webby_config = vl.Config(webby.WebbyFile, packages=[webby.pkg, webby_gzip.pkg], loader=read_file)


def run_webby(applied: vl.Applied | None) -> vl.Applied | None:
    result = webby_config.load("webby.conf", applied=applied)
    if isinstance(result, vl.Rejected):
        return applied
    for s in result.value.servers:
        print(s.name, [listen.ports for listen in s.listen], s.types.by_extension.get("html"))
    gzip_failures = webby_gzip.apply(result.changes, lambda at, on: None)  # gzip applies its own
    return result.applied(handles=[webby.Server, webby_gzip.Gzip], failures=gzip_failures)


if __name__ == "__main__":
    print(rasl_config.describe())  # runs for real: declarations and the startup check
    print(webby_config.describe())
```

`describe()` really runs. Its output is in `evidence/describe.txt`. `load` is a stub with no
parser. The test kit (`knobly.testing.build`) builds the same records from hand-written lines,
and `evidence/runtime.txt` shows the rasl config and the webby config above built for real. That
output covers inherited values, the node type picked, plain data lines, gzip applied by its own
module, and 10 errors each placed at its line.

---

## Open questions for the owner (the design rests on these; none is adopted silently)

1. **A holder's field is the permission to write a directive there.** Round 9 let a directive
   name the blocks it may be written in. Here, any package whose record has a field typed with a
   directive may hold it, and that directive's author cannot forbid it.
2. **Repetition belongs to the holder's field** (`tuple[Header, ...]`), not to `many=` on the
   directive.
3. **No scope objects.** "A group holds what a graph holds" is two field lists, plus
   `rasl.GRAPH_BLOCKS = (Graph, Group)` for a third party placing a directive in both.
4. **An inheriting directive's default lives only in the directive.** A holder cannot give it a
   different default.

## What this costs

- The checkers do not hold a node type to `NodeKind`. That check happens only at program start.
- The record built from the config is also the program's domain type.
- A directive with one value is still a record, so reads unwrap: `graph.fps.rate`.
- A hand-built record must pass its inheriting fields: `Graph(fps=Fps())`.
- `_: KW_ONLY` is correct stdlib Python, but most dataclass users have never seen it.
