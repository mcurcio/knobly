# Round 10, TypeScript: a directive is a Nest route handler

The owner said on 2026-10-28: "They are trying to combine the inspirations rather than choosing one
model". This binding uses one model only: NestJS. A package is a `@Module`. A kind of block is a
class under `@Scope`, as a Nest controller is. **Each method is a directive**: its name is the
directive's name, its parameters are the values written after it, and what it returns is what the
program reads. Each value's type is written once, on its parameter; tsc hands that type to the
runtime through `reflect-metadata` (his 2026-10-28 steer: "third party libraries are ok for things
like reflect-metadata").
- `@Value` marks a value that must be written. `@Optional` marks one that may be left out: it has a
  default (`= 512`), or a `?` when absent means undefined. tsc refuses either one in the wrong place.
- `...ports: number[]` takes one or more values. A class of `@Flag` booleans holds the flag words.
- `@Body(SomeScope) block` opens a block of that kind; `@Body() lines` reads a block raw.
- A scope class that `extends` another holds that one's directives too.

Every code block below is copied from a checked file under `round10/final-ts/`. tsc 6.0.3 strict
exits 0 on it (`evidence/good.txt`), and `node out/app.js` runs it (`evidence/run-app.txt`).
"Excerpt" marks a block with lines left out; the left-out lines are named.

---

## 1. A web server's directives (`webby/index.ts`, excerpt: imports, the `Listen`/`Route`/`Server` result types, `Duration` and `AbsolutePath` left out)

The config these serve (`configs/webby.conf`, whole file):

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

```ts
export class ListenModes {
  @Flag("Serve over TLS.") tls = false;
  @Flag("Allow HTTP/2.") http2 = false;
}

/** What a server and a location both hold. Each extends it, as plain TS classes do; a plugin may join it. */
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

@Scope("server", { doc: "One virtual server." })
export class ServerBody extends RouteBody {
  @Directive("Ports, then modes: listen 8080 443 tls http2. May repeat.", { many: true })
  listen(@Flags() modes: ListenModes, @Value("Port numbers.", new IntPipe({ min: 1, max: 65535 })) ...ports: number[]): Listen {
    return { ports, tls: modes.tls, http2: modes.http2 };
  }

  @Directive("A MIME type, then the extensions that map to it: types { text/html html htm; }.")
  types(@Body() lines: Lines): Map<string, string> {
    return new Map(lines.flatMap((l) => l.words.map((ext) => [ext, l.name] as const)));
  }
}

@Scope(Root)
export class WebbyRoot {
  @Directive("One virtual server: server example { ... }.")
  server(@Key("Unique among servers.") name: string, @Body(ServerBody) block: Block): Server {
    return {
      name,
      listen: block.all(ServerBody, "listen"),
      root: block.get(ServerBody, "root"),
      types: block.get(ServerBody, "types") ?? new Map(),
      routes: block.all(ServerBody, "location"),
    };
  }
}

@Module({ doc: "A small web server.", scopes: [WebbyRoot, RouteBody, ServerBody, LocationBody] })
export class WebbyModule {}
```

How to read these:
- `listen 8080 443 tls http2`: the numbers fill `...ports`, each checked by `IntPipe` to be from 1
  to 65535, and `tls` and `http2` are the flag words of `ListenModes`. `many: true` lets it repeat.
- `RouteBody` holds what a server and a location both hold. `ServerBody` and `LocationBody`
  extend it, so `root`, `header` and `location` are written once.
- `root` is `inherit: true`: a location that does not write it reads the nearest one written around
  it, else the default `/var/www/html`, stated once on the parameter.
- `location` takes a `@Key`, so locations may repeat and two with the same path are refused (E5009, run on rasl's `node`).
  `AbsolutePath` is a pipe: `location api` would be refused at that value (no config here tries it). Its block is a
  `LocationBody`, which extends `RouteBody`, so it is named through Nest's `forwardRef`.
- `types` reads its block raw (`@Body() lines`): its lines are data, not directives.

## 2. A nested, repeated directive: rasl's `group` (`rasl/graph.ts`, whole file)

The config (`configs/family_room.conf`, excerpt: lines 15 to 39, the `graph` block):

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

```ts
// The graph: a scope class per kind of block; each method is a directive written in it.
// A scope class that extends another holds its directives too: graphs, groups and nodes all hold `fps`.
import { Block, Body, Chosen, Directive, Key, Optional, Scope, Value } from "knobly";
import { GroupSpec, type Connection, type NodeHead, type NodeSpec } from "./domain.js";
import { Endpoint, Rate } from "./values.js";

@Scope("timing", { doc: "What graphs, groups and nodes all hold." })
export class Timing {
  @Directive("Frames per second. Inner blocks read the nearest one written.", { inherit: true })
  fps(@Optional("30 or 30hz.") rate: Rate = new Rate(30)): Rate {
    return rate;
  }
}

@Scope("node", { doc: "What every node block holds, whatever its type." })
export class NodeBody extends Timing {
  @Directive("Feed this node from another's output: connect twinkle[0:144] pixels.", { many: true })
  connect(@Value("A node, node.port, or a slice.") source: Endpoint, @Optional("The input it feeds; the node's first when absent.") to?: string): Connection {
    return { source, input: to };
  }
}

/** `node <type> <id>`: the type word picks a directive placed in this scope, from any package. */
@Scope("node type", { doc: "The word after `node`. A package adds a node type by placing a directive here." })
export abstract class NodeType extends Chosen<NodeHead, NodeSpec> {}

/** What every node type builds first: its id and type, then rasl's fps and connections read from its block. */
export function nodeSpec(head: NodeHead, block: Block): NodeSpec {
  return { ...head, fps: block.get(NodeBody, "fps"), connections: block.all(NodeBody, "connect") };
}

@Scope("graph", { doc: "What a graph or a group holds." })
export class GraphBody extends Timing {
  @Directive("node <type> <id> { ... }: one node of the graph.")
  node(@Value("The node type, from any package.") type: NodeType, @Key("Unique among its siblings.") id: string): NodeSpec {
    return type.build({ id, type: type.name }); // builds the picked type, which reads its own block
  }

  /** Recursive: a group's block is a graph block. Its return type is written: TS cannot infer a value that reads itself. */
  @Directive("A named group of nodes. Groups nest: a group's block is a graph block.")
  group(@Key("Unique among its siblings.") id: string, @Body(GraphBody) block: Block): GroupSpec {
    return new GroupSpec(id, block.all(GraphBody, "node", "group")); // in written order
  }
}
```

- `group` opens a `GraphBody` block, so a group holds what a graph holds, including another group.
  Its `@Key` id makes it repeat; the same id twice among siblings is refused.
- `block.all(GraphBody, "node", "group")` reads both in the order written.
- `fps` sits in `Timing`, which `GraphBody` and `NodeBody` extend. It is `inherit: true`, so each
  graph, group and node reads the nearest `fps` written around it, else 30.
- `connect`'s `to?: string` is `@Optional` with no default: absent means undefined.
- `node Waveform hue_ramp`: `type: NodeType` is a select scope. The word after `node` picks a
  directive placed in `NodeType` by any package; `type.build(...)` runs it, and `type.name` is the
  word written.

A third party adds a node type (`rasl-waveform/index.ts`, whole file):

```ts
// A third-party node type for rasl: `node Waveform hue_ramp { shape sine; }`.
// It places a directive in rasl's `node type` scope and reads rasl's fps; rasl never names it.
import { Block, Body, ConfigError, Directive, Head, Module, Optional, RangePipe, Scope, choice, type Choice, type DynamicModule } from "knobly";
import { NodeBody, NodeType, RaslModule, nodeSpec, type NodeHead, type NodeSpec } from "../rasl/index.js";

/** Handed in by the program: WaveformModule.register({ maxFrequencyHz: 50 }). */
export class WaveformOptions {
  maxFrequencyHz = 1000;
}

export const Shape = choice("A wave's shape.", "sine", "sawtooth", "square");
export type Shape = Choice<typeof Shape>;

@Scope("Waveform", { doc: "A Waveform node's block." })
export class WaveformBody extends NodeBody {
  constructor(private readonly options: WaveformOptions) {
    super(); // options are injected by type, as in Nest
  }

  @Directive("The wave's shape. Changing it restarts the node.", { restart: true })
  shape(@Optional("sine, sawtooth or square.") shape: Shape = "sine"): Shape {
    return shape;
  }

  @Directive("Cycles per second.")
  frequency_hz(@Optional("0 up to the program's limit.", new RangePipe({ min: 0 })) hz: number = 1): number {
    if (hz > this.options.maxFrequencyHz) throw new ConfigError(`at most ${this.options.maxFrequencyHz} Hz here`, { code: "waveform/too-fast" });
    return hz;
  }
}

export interface WaveformSpec extends NodeSpec {
  readonly shape: Shape;
  readonly frequencyHz: number;
}

@Scope(NodeType)
export class WaveformType {
  @Directive("A periodic signal, one value per output channel.")
  Waveform(@Head() head: NodeHead, @Body(WaveformBody) block: Block): WaveformSpec {
    return {
      ...nodeSpec(head, block), // rasl's part: id and type from `node`, fps (here, else the nearest block, else 30), connect
      shape: block.get(WaveformBody, "shape"),
      frequencyHz: block.get(WaveformBody, "frequency_hz"),
    };
  }
}

@Module({ doc: "Periodic signals for rasl.", imports: [RaslModule], scopes: [WaveformBody, WaveformType], providers: [WaveformOptions] })
export class WaveformModule {
  /** Nest's dynamic module: the program sets this package's knobs where it imports it. */
  static register(options: Partial<WaveformOptions>): DynamicModule {
    return { module: WaveformModule, providers: [{ provide: WaveformOptions, useValue: Object.assign(new WaveformOptions(), options) }] };
  }
}
```

`WaveformBody extends NodeBody`, so a Waveform block holds rasl's `connect` and `fps`. Changing
`shape` restarts the node (`restart: true`). The program sets `maxFrequencyHz` where it imports the
package, as a Nest dynamic module.

## 3. The plugin: webby-gzip adds `gzip` to webby's blocks (`webby-gzip/index.ts`, whole file)

```ts
// package webby-gzip: adds `gzip` to webby's blocks, which it does not own, and applies its own
// changes (nginx: each module reads its own conf). webby never names it.
import { Directive, Injectable, Module, OnChange, Optional, Scope, Value, type Change } from "knobly";
import { RouteBody, WebbyModule } from "../webby/index.js";

/** Joins webby's route scope, so `gzip` may be written in every server and location. */
@Scope(RouteBody)
export class GzipDirectives {
  @Directive("Compress responses: gzip on. Inner locations read the nearest one.", { inherit: true })
  gzip(@Optional("true or false.") on: boolean = false): boolean {
    return on;
  }
  @Directive("MIME types to compress: gzip_types text/html application/json.", { inherit: true })
  gzip_types(@Value("MIME types.") ...types: string[]): string[] {
    return types;
  }
}

@Injectable()
export class GzipService {
  readonly log: string[] = [];
  @OnChange(GzipDirectives, "gzip")
  turn(change: Change<boolean>): void {
    this.log.push(`gzip ${change.kind} at ${change.path}: ${change.kind === "removed" ? "off" : change.value}`);
  }
}

@Module({ doc: "Response compression for webby.", imports: [WebbyModule], scopes: [GzipDirectives], providers: [GzipService] })
export class GzipModule {}
```

webby never names this package. `@Scope(RouteBody)` places `gzip` in every block that extends
`RouteBody`: servers and locations. `GzipService` is a provider; its `@OnChange` method runs for each
change to `gzip`, as Nest's `@OnEvent` does.

## 4. The program side (`app.ts`, whole file)

```ts
// Two programs, Nest-style: a root module imports the packages it uses and provides the
// handed-in things (the loader, a package's options); providers react to changes.
import { ChangeFailed, Injectable, Loader, Module, OnChange, KnoblyFactory, formatDiagnostic, type Change, type Loaded } from "knobly";
import { IncludeModule } from "knobly/include";
import { FileLoader } from "./io.js";
import { GraphBody, RaslModule, RaslRoot, type NodeSpec, type Rate, type UiSpec } from "./rasl/index.js";
import { WaveformModule } from "./rasl-waveform/index.js";
import { WebbyModule, WebbyRoot, type Server } from "./webby/index.js";
import { GzipModule, GzipService } from "./webby-gzip/index.js";

const configs = new URL("../configs", import.meta.url).pathname;

// ── rasl ──

@Injectable()
export class Engine {
  @OnChange(GraphBody, "node")
  node(change: Change<NodeSpec>): void {
    if (change.kind === "removed") return void console.log(`  stop ${change.previous.id}`);
    if (change.kind === "added" && change.value.id === "ember") throw new ChangeFailed("no free output for ember");
    const v = change.value;
    console.log(`  ${change.kind === "replaced" ? "restart" : change.kind === "added" ? "start" : "retune"} ${v.type} ${v.id} at ${v.fps.hz} fps  (${change.path})`);
  }
  @OnChange(GraphBody, "fps")
  fps(change: Change<Rate>): void {
    console.log(`  frame clock ${change.kind} at ${change.path}`);
  }
  @OnChange(RaslRoot, "ui")
  ui(change: Change<UiSpec>): void {
    if (change.kind !== "removed") console.log(`  ui ${change.kind}: ports ${change.value.ports.join(" ")} dev=${change.value.dev} tls=${change.value.tls}`);
  }
}

@Module({
  doc: "The rasl program.",
  imports: [RaslModule, WaveformModule.register({ maxFrequencyHz: 50 }), IncludeModule.register({ maxDepth: 16 })],
  providers: [Engine, { provide: Loader, useValue: new FileLoader(configs) }],
})
export class RaslApp {}

function report(file: string, loaded: Loaded): void {
  if (loaded.status === "rejected") {
    console.log(`${file}: rejected, ${loaded.diagnostics.length} problem(s); keep running what runs`);
    for (const d of loaded.diagnostics) console.log(formatDiagnostic(d, loaded).replace(/^/gm, "  "));
  }
}

export async function runRasl(host: string): Promise<void> {
  const app = await KnoblyFactory.create(RaslApp); // throws DeclarationError listing every problem
  console.log("── describe()\n" + app.describe());
  for (const file of ["family_room.conf", "family_room.v2.conf", "family_room.bad.conf"]) {
    console.log(`── load ${file}`);
    const loaded = await app.load(file, { variables: { host } });
    if (loaded.status === "rejected") {
      report(file, loaded);
      continue;
    }
    const graph = loaded.root.get(RaslRoot, "graph");
    console.log(`  graph at ${graph?.fps.hz} fps, ${graph?.items.length} top-level items`);
    const applied = await app.apply(loaded); // runs Engine's @OnChange methods
    for (const f of applied.failures) console.log(`  FAILED ${f.change.path}: ${f.reason}`);
    for (const c of applied.notApplied) console.log(`  not applied (nothing handles it): ${c.kind} ${c.path}`);
  }
}

// ── webby ──

@Injectable()
export class Sites {
  @OnChange(WebbyRoot, "server")
  server(change: Change<Server>): void {
    if (change.kind !== "removed") console.log(`  ${change.kind} server ${change.value.name}: ${change.value.routes.map((r) => r.path).join(", ")}`);
  }
}

@Module({ doc: "The webby program.", imports: [WebbyModule, GzipModule], providers: [Sites, { provide: Loader, useValue: new FileLoader(configs) }] })
export class WebbyApp {}

export async function runWebby(): Promise<void> {
  const app = await KnoblyFactory.create(WebbyApp);
  console.log("── load webby.conf");
  const loaded = await app.load("webby.conf");
  if (loaded.status === "rejected") return report("webby.conf", loaded);
  for (const s of loaded.root.all(WebbyRoot, "server")) console.log("  " + JSON.stringify(s, (_k, v: unknown) => (v instanceof Map ? Object.fromEntries(v) : v)));
  const applied = await app.apply(loaded);
  console.log("  " + app.get(GzipService).log.join("\n  "));
  for (const c of applied.notApplied) console.log(`  not applied (nothing handles it): ${c.kind} ${c.path}`);
}

await runRasl("10.0.60.30");
await runWebby();
```

What a second load prints (`evidence/run-app.txt`, excerpt: the `family_room.v2.conf` load only):

```text
── load family_room.v2.conf
  graph at 30 fps, 4 top-level items
  restart Waveform hue_ramp at 30 fps  (/graph/node:hue_ramp)
  retune TwinkleEffect twinkle at 20 fps  (/graph/group:fireplace/group:mantel/node:twinkle)
  stop leds
  FAILED /graph/group:fireplace/node:ember: no free output for ember
```

- `KnoblyFactory.create` checks every declaration before any config is read and lists every
  problem at once (`evidence/planted-startup.txt`).
- `load` returns `accepted` or `rejected`; only an accepted load has a `root` to read (tsc refuses
  the other, `planted/p5-program-side.ts`).
- `apply` runs the `@OnChange` methods for each change since the last apply. A handler throws
  `ChangeFailed` for a change it could not apply; any other error is a bug and propagates.
  **Open choice for the owner:** this replaces his v6 pick `applied(failures)`.

## 5. What tsc refuses (`planted/p1-erased-value-types.ts`, excerpt: the last two of six planted directives)

```ts
  @Directive("A `?` value declared with @Value (the runtime cannot see `?`).")
  fade(@Value("Milliseconds.") ms?: number): number { // EXPECT: may be left out: declare it with @Optional
    return ms ?? 250;
  }
  @Directive("A required value declared with @Optional.")
  seed(@Optional("Seed.") seed: number): number { // EXPECT: must be written: declare it with @Value
    return seed;
  }
```

tsc, from `evidence/planted-p1-erased-value-types.txt` (excerpt: these two errors only):

```text
planted/p1-erased-value-types.ts(23,9): error TS1239: Unable to resolve signature of parameter decorator when called as an expression.
  Argument of type '0' is not assignable to parameter of type '0 & Refused<"this value may be left out (it has a default or a ?): declare it with @Optional">'.
planted/p1-erased-value-types.ts(27,9): error TS1239: Unable to resolve signature of parameter decorator when called as an expression.
  Argument of type '0' is not assignable to parameter of type '0 & Refused<"this value must be written: declare it with @Value, or give it a default or a ?">'.
```

Not caught by tsc: a read of a directive from a block that can never hold it, and `get()` on a
repeating directive. Both are reported at load, and only when a config reaches that code
(`evidence/planted-load-time.txt`). NOTES.md lists the rest.
