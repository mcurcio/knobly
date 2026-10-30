# Knobly: one model per language (v10)

**Status:** draft v10 for your review (gate kno-9vn) · **Layer:** **[ System design ]** › Module › Feature

**What you are asked:** do these read right? Two more questions, each under its language: how a Python block lists what it holds (§2), and how a TypeScript read names its block (§3).

---

## Since your answers of 2026-10-28

| You said (page v9) | What v10 does |
|---|---|
| "both a bit schizophrenic … trying to combine the inspirations rather than choosing one model" | Each language now follows **one** library's model all the way. 5 candidates were built, one per model; a reviewer per language tried to break them and picked one |
| "The idea that typescript “has to be written twice” is problematic." | **TypeScript is now NestJS**: each value's type is written once, on its parameter. A real tsc + Node run shows the runtime reading it |
| "third party libraries are ok for things like reflect-metadata" | TypeScript uses `reflect-metadata`. R19 is amended to say so; pydantic stays an optional extension |
| startup · whole | Kept. Python now catches a wrong-block read **when it type-checks**; TypeScript does not yet (§3) |

| Language | Candidates built | Picked | Why (reviewer's score out of 60) |
|---|---|---|---|
| Python | Typer/FastAPI functions · **dataclasses** | dataclasses (45 vs 34) | A directive's fields are what is written; reads are plain typed attributes. Typer needed a function per one-value directive and restated every read's type |
| TypeScript | **NestJS** · commander · typia (types read by a compiler plugin) | NestJS (46 vs 45 vs 40) | The only one with each type written once that also ran all five programs. commander still wrote each value's name twice; typia needs a compiler plugin and covered least |

---

## 1. The config being declared (webby; rasl's is v9's, unchanged)

```nginx
set $backend "http://10.0.0.5:8080";
snippet cors $origin { header Access-Control-Allow-Origin $origin; }

server example {
    listen 8080 443 tls http2;
    root /var/www;
    gzip true;                                 # from another package
    location /api {
        proxy $backend;
        use cors "*";
        location /api/v2 { timeout 30s; }      # locations nest
    }
    types { text/html html htm; application/json json; }
}
```

---

## 2. Python: a directive is a dataclass

`@vl.directive` makes a frozen dataclass. **Its fields are what is written:** fields before `_: KW_ONLY` are the values in order; after it, a `bool` is a flag word, a field typed with a directive is a line of the block, a `tuple[...]` of them may repeat. `vl.field(...)` carries doc, bounds and key, as `dataclasses.field` does. The record is what the program reads.

`webby/__init__.py` (excerpt: `Server`, `Types`, value types and `pkg` left out)

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

A package that does not own the block joins it by naming it (`webby_gzip/__init__.py`, excerpt: `GzipTypes` and `apply` left out):

```python
@vl.directive(inside=[webby.Server, webby.Location], inherit=True)
class Gzip:
    """Compress responses: gzip true. Inner locations read the nearest one."""

    on: bool = False  # a value before KW_ONLY: written `gzip true`, not a flag word
```

A third-party rasl node type joins by `select=` (`rasl_waveform/__init__.py`, excerpt):

```python
@vl.directive("Waveform", select=rasl.NodeKind)
class Waveform:
    """A periodic signal, one value per output channel."""

    _: KW_ONLY
    fps: rasl.Fps  # rasl's fps: here, else the nearest block, else 30
    inputs: tuple[rasl.Connect, ...] = ()
    shape: Shape = Shape()
    frequency_hz: FrequencyHz = FrequencyHz()
```

The program side keeps your v6 pick, `applied(failures)` (`app.py`, excerpt: the rasl half):

```python
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
```

[[Q:pyholds]]

---

## 3. TypeScript: a directive is a Nest route handler

A package is a `@Module`; a kind of block is a `@Scope` class, as a Nest controller is. **Each method is a directive:** its name is the directive's name, its parameters are the values, its return is what the program reads. `@Value` must be written, `@Optional` may be left out; a scope class that `extends` another holds its directives too.

`webby/index.ts` (excerpt: `ServerBody`, `WebbyRoot`, the module and result types left out)

```ts
@Scope("route", { doc: "What a server and a location both hold." })
export class RouteBody {
  @Directive("Serve files from here. Inner locations read the nearest one.", { inherit: true })
  root(@Optional("A directory.") path: string = "/var/www/html"): string {
    return path;
  }

  @Directive("Add a response header.", { many: true })
  header(@Value("Header name.") name: string, @Value("Header value.") value: string): readonly [string, string] {
    return [name, value];
  }

  /** LocationBody extends this class, so it is named through Nest's forwardRef. */
  @Directive("Serve a path prefix. Locations nest.")
  location(@Key("Starts with /.", new AbsolutePath()) path: string, @Body(forwardRef(() => LocationBody)) block: Block): Route {
    return {
      path,
      root: block.get(LocationBody, "root"),
      proxy: block.get(LocationBody, "proxy"),
      timeoutMs: block.get(LocationBody, "timeout")?.ms,
      headers: block.all(LocationBody, "header"),
      children: block.all(LocationBody, "location"),
    };
  }
}

@Scope("location", { doc: "A path prefix and what it serves." })
export class LocationBody extends RouteBody {
  @Directive("Pass requests on to this URL.")
  proxy(@Value("Quoted or bare.") url: string): string {
    return url;
  }
  @Directive("Give up on the upstream after this long: timeout 30s.", { inherit: true })
  timeout(@Value("250ms, 30s or 5m.") after: Duration): Duration {
    return after;
  }
}
```

`listen 8080 443 tls http2` is a rest parameter plus a flags class (excerpt from `ServerBody`):

```ts
  @Directive("Ports, then modes: listen 8080 443 tls http2. May repeat.", { many: true })
  listen(@Flags() modes: ListenModes, @Value("Port numbers.", new IntPipe({ min: 1, max: 65535 })) ...ports: number[]): Listen {
    return { ports, tls: modes.tls, http2: modes.http2 };
  }
```

The plugin joins webby's shared scope (`webby-gzip/index.ts`, excerpt: `gzip_types` and the module left out):

```ts
@Scope(RouteBody)
export class GzipDirectives {
  @Directive("Compress responses: gzip on. Inner locations read the nearest one.", { inherit: true })
  gzip(@Optional("true or false.") on: boolean = false): boolean {
    return on;
  }
```

```ts
@Injectable()
export class GzipService {
  readonly log: string[] = [];
  @OnChange(GzipDirectives, "gzip")
  turn(change: Change<boolean>): void {
    this.log.push(`gzip ${change.kind} at ${change.path}: ${change.kind === "removed" ? "off" : change.value}`);
  }
}
```

The program is a root `@Module`; `KnoblyFactory.create(RaslApp)` checks every declaration at startup, `app.load(file)` reads, `app.apply(loaded)` runs the `@OnChange` methods, and a handler throws `ChangeFailed` for a change it could not apply.

[[Q:tsread]]

---

## 4. Do these read right?

| | Python (dataclasses) | TypeScript (NestJS) |
|---|---|---|
| Concepts to learn | 13 (most are dataclass's own) | 11 (9 are Nest's own) |
| Each type written | once | once (proved by a run) |
| Good code | pyright 0, mypy 0 | tsc 0; the app runs all five programs |
| Planted mistakes caught by the checker | 12 of 12 | 14 errors over 5 files |
| Caught when the program starts | 14 of 14 more | 10 of 10 more |
| Wrong-block read | caught by the checker | caught only at load (§3) |
| Caught nowhere | a package writing its directive in another package's wrong block; a misspelled `at="..."` | two same-typed values swapped; a wrong block of an imported package |

[[Q:read]]

[[REST:interfaces]] The rest is recommended as shown: TypeScript reports changes through `@OnChange` handlers (Nest's `@OnEvent`) instead of your v6 pick `applied(failures)`, which Python keeps; Python checks a node type against `NodeKind` only at startup; a one-value Python directive is still a record, so reads unwrap (`graph.fps.rate`).

---

## 5. Costs, NOT RUN, next

**Costs**
- TypeScript needs legacy decorators and a compile step. esbuild (used by tsx and vitest's default setup) drops the type metadata; an app built with it stops at startup with a clear error instead of misreading values (run). Tests need tsc or swc (swc NOT RUN). The TS 7 preview emits the metadata and runs (run).
- TypeScript directive names are method names (`max_count`), against TS naming style.
- Python's `_: KW_ONLY` is correct stdlib, but most dataclass users have never seen it.
- Python: the record built from the config is also the program's domain type.

**NOT RUN:** no parser for the new grammar exists, so no config file has gone through `load`. Python's test kit builds the records from hand-written lines; TypeScript's prototype runtime reads a subset of the grammar. Not run: ruff, editor hovers, any Python but 3.11, any TS but 6.0.3 and the TS 7 preview.

**Next, on your answers:** fix the language faults L1–L8, then a parser and a tracer that loads rasl's real configs through both APIs.

*History: v1–v8 the model and grammar · v9 one style per language from surveyed references · v10 one model per language (dataclasses, NestJS).*
