# Consumer API — requirements (working state, not a deliverable)

Gate bead: vil-9vn. Layer: SYSTEM DESIGN (domain model + public interfaces only).
Scope: vil-9ze (typed values), vil-stq (DirectiveDelegator), vil-xlo (declarative definitions),
vil-bgz (include view), vil-bzv (diagnostics reporting), as ONE consumer API, TS and Python.

## Requirements (binding; source on each)
- R1 Layers: "An EBNF gives a language independent syntax. And then parsers can be written against it, and then finally language-specific idiomatic sugar APIs can be layered on top". Owner 2026-10-21; design/RECORD.md R3.
- R2 "the TS *config* is canonical. The python version of the full runtime is still more comprehensive". Owner 2026-10-21; RECORD R4.
- R3 The five epics are one surface. Owner 2026-10-24 ("All five"), vil-9vn.
- R4 Slice bounds "Integers only"; other bounds are located error E4001. Owner 2026-10-23, vil-9ze.3.
- R5 `foo[1]` is "Its own kind: index". Owner 2026-10-23, vil-9ze.2.
- R6 A bad line is one error node, later siblings kept; nesting >100 is E2010. Owner 2026-10-23, vil-bzv.3. API serves partial trees.
- R7 Value typing: "The directive schema, where possible". Owner 2026-10-24, vil-9vn. (Requirements step recommended: villanelle returns words; a declared definition asks for a type and villanelle applies its one rule for it, with a located error.)
- R8 include: "Shouldn't be baked in, or should it be a first-party plugin/extension? How will includes be round-tripped through modifications to an included subtree?" Owner 2026-10-24, vil-9vn. Current reading (main session, to confirm on the gate page): include ships with villanelle as a first-party extension a program turns on, not hard-coded in core; the design must show how an edit to a directive reached through an include lands in the included file (the editing API itself is vil-uji, not this gate, but this design must not preclude it).
- R9 Python and TS both: "Both, idiomatic in each language. Python should take inspiration from pydantic, as that's the natural Python configuration mechanism." Owner 2026-10-24, vil-9vn.
- R10 Typed value with span for every argument; rasl's coerceScalar and parseSliceTokens deletable (vil-9ze acceptance).
- R11 Delegator (vil-stq, rasl plans/scope.md): children walked by default; handler result typed: children / childrenWith / skip; no unknown casts; async handlers; handlers report diagnostics; hooks onEnterScope, onExitScope, onBeforeDirective, onAfterDirective, onUnknownDirective, onSkipDirective; no shims. (These are bead text, not owner quotes: revisable with reason.)
- R12 Declarative definitions (vil-xlo; nextgen.md §5; scope.md §6): declare name, argument types, allowed children; get typed output + located diagnostics; thin layer over the delegator; TS accepts any Standard Schema validator (zod test).
- R13 Include view (vil-bgz): include replaced in place by its targets' directives, nesting kept; engine reads nodes from included files. Shipped TS include rules: quoted paths, loader port, code-point sort, depth 16 (E3003), cycles stop, loader failure is a diagnostic, included files stay separate document nodes so each round-trips.
- R14 Diagnostics (vil-bzv; nextgen.md): 0-based line/col, stable code, message; include diagnostics carry source identity and include directive span; report(directive, message, code?) helper.
- R15 Three tiers: token/CST, directive facade, minimal registration (nextgen.md §5).
- R16 Core does no I/O (ts/src/index.ts:1-4; include.md).
- R17 TS and Python identical in codes, spans and trees (RECORD soundness (b); ts/src/diagnostics.ts:4-5).
- R18 rasl acceptance: rasl-ccm (rasl.ts uses include view, typed values, definitions; drops own coercion, slice parsing, IRaslConfigError); rasl-95b.4 (each node class declares a config schema validated at load with located errors; "unit parsing stays at the engine edge"); rasl-ynq (errors print file:line:col: message, source line, caret).

## Conflicts found (resolve or raise)
- C1 Values: vil-9ze says word,string,number,list,slice; shipped Value (ts/src/value.ts:56) is word,string,slice,index; list throws (value.ts:74-75); EBNF has NumberText/BooleanText (grammar/villanelle.ebnf:52-56) unused; rasl Python treats on/yes/off/no as bool (rasl src/rasl/config/loader.py:28-48). R7 steers this.
- C2 include core vs registered (nextgen "include is core"; parse-graph.ts:56, iterate.ts:21 hard-code it; vil-bgz says registered; E2006 syntax code emitted by graph layer). R8 steers this.
- C3 IDiagnostic.code only villanelle codes (diagnostics.ts:47-48); no severity (rasl filters severity==="error", rasl.ts:276); only IGraphDiagnostic knows its file (graph.ts:31-34).
- C4 vil-bzv stale: include diagnostics already use directive span; W3005 undefined.
- C5 villanelle never shipped the delegator (reference/rasl-config-ts/src/delegator.ts only). vil-stq "delete scope.md" contradicts "don't delete the plans".
- C6 Same file included twice is parsed once (parse-graph.ts:93-97); view would show the same directive object at two positions; rasl keys data on directive identity (rasl.ts:356, dispatch.py:194).
- C7 Python has no include graph, loaders or delegator (py/README.md:24).
- C8 nextgen.md stale on lexical rules; the RECORD and grammar win.
- C9 include.md says parse async-only; shipped sync parse/parseDocument + async parseGraph; vil-m8w.3 open.
- C10 Standard Schema is JS-only; rasl Python uses Pydantic (dispatch.py:79-108). R9 steers this.

## Terms
Existing (reuse): Directive, Document, DirectiveList (body, children), Argument (ts/src/ast/ast.ts:12-59); Value, ValueKind, ValueRef (value.ts; cst.ts:51); Syntax, Node, NodeKind (cst.ts:38); Span, Position (span.ts); Diagnostic, DiagnosticCode, DiagnosticError (diagnostics.ts); document graph, document node, edge, resolvedPath, spec, loader, writer (graph/graph.ts, io.ts); DirectiveDelegator, handler, hooks, ctx, legal directives (reference/rasl-config-ts/src/delegator.ts); Delegate.children/childrenWith/skipChildren (scope.md §5).
Collisions: "scope" (delegator instance vs document-or-block); "node" (CST node, graph node, rasl `node` directive); "graph" (document graph vs rasl `graph` block); "depth limit" (include 16/E3003 vs nesting 100/E2010).
Likely new: inlined view (include.md's "single inlined document view"); directive definition; severity (only if needed); include chain.

## What rasl needs
TS engine (rasl js/packages/engine/src/config/rasl.ts): two named root blocks graph/ui, others ignored (242-264); two passes over graph (create nodes, then connect; forward refs), data passed via monkey-patched __raslConnects (296-398); positional args by kind: `node <Type> <id> [model] [data]`, `color:hsl` one word (319-339); nested number lists with comments/trailing commas; `connect a.port[0:3] b[0:3]` with `repeat N` body (120-183); open property sets: unknown child -> property, no args -> true, `20 hz` -> "20hz", snake->camel, `ports {}` children read as names (47-63, 102-109, 225-240); collects many errors, continues; includes ignored (graph.root only, 284); CLI prints "Line N".
Python (rasl src/rasl/config/): all args strings coerced to bool/int/float/unquoted string (loader.py:28-48); block flattened to dict: no args -> true, repeated key -> list, nested block with args gets id, key->line map (loader.py:51-139, 206-223); positional arg counts per node type (262-328); @config(keyword, model=) handlers return domain objects collected per keyword, arg_fields maps positions to fields, unknown keyword is error (dispatch.py:79-214) — a working Pydantic-based definitions layer; stops at first error, 1-based line, caret (dispatch.py:19-75); `[n]` re-parsed as n..n+1 (connect_parser.py:160-205).

## Edge cases to answer at this layer (or defer by name)
include inside a block and which handlers apply to its targets; same file included twice (C6); cycles; unresolved include in the view; file + included-from chain on diagnostics from included directives; collect-all vs stop-first; consumer codes namespace; severity; validator failure -> span on the right argument; 0-based internal vs 1-based display; UTF-16 columns (vil-10c); async order and exceptions; async in Python; unknown directives open vs closed per scope; directive names as data (`ports`); values `8080`, `true`, `on`, `20hz`, `-0`, nested/empty lists, trailing comma; undeclared values; partial trees and whether handlers run when syntax errors exist.
Existing open owner decisions the architect should propose answers for (not add questions): vil-bzv.2, vil-stq.1, vil-stq.2, vil-m8w.3, vil-n1j, vil-10c.

## Owner gate answers, 2026-10-25 (gate page + chat; verbatim in vil-9vn) — these supersede the drafts' current choices
- R19 No third-party dependencies in core: "I don't want villanelle dependent on third party libraries (including pydantic) so any shims must be optional extensions rather than core." Also: "JSON scheme is a nice foundation, where it works." (Q1 note, 2026-10-25). R9's "take inspiration from pydantic" stays: inspiration, not a dependency.
- R20 Include: "I think it's a first-party plugin/extension. And any configuration knobs that "includes" may require could be set when the plugin is instantiated and passed into the config tool." (R8 note, 2026-10-25)
- R21 A file included at two places is allowed, per place: owner chose "Allowed, per place" (2026-10-25). His note: "Obviously the file only needs to be read once, and any core syntax errors can be communicated once. But reading the file is probably different than interpreting the contents, for example if the file is included into a context where the included directives don't apply, then the syntax of the included file is correct but it will produce errors when the content is applied to its parent scope."
- R22 Include variables: "Leave room only" (2026-10-25): no variable syntax now (bead filed), but each place must be able to carry its own bindings later. His note: "if we allow variables to passed into the included file, then each instance of the file would have its own bindings."

## Owner gate answers v2, 2026-10-26 (gate/answers-v2; verbatim in vil-9vn) — supersede earlier choices
- R23 "The core library APIs shouldn't be built around third party libraries. For example, a pydantic integration should be an optional plugin wrapper around the native Python villanelle API. That is, there should be an idiomatic SPI for each supported language, *and optionally* additional integration APIs for common languages frameworks." (Q1 note). Main-session reading, to confirm: the ANTLR runtime (internal, not part of the API a program meets) may stay; each language's native API is the extension point (SPI = service provider interface: the hooks an extension implements).
- R24 "JSON schema may be one of the configuration mechanisms, it it can't be the only one because it is not conducive to building natural APIs that are idiomatic in each target language." (Q2 note). So core's definitions are native per language; JSON Schema is at most one optional mechanism over them.
- R25 Scope: no extensions in this epic. "Focus on the core, low level API and high level sugar APIs. The extensions can come later as additional sugar." (Q3, picked C). pydantic, zod/Standard Schema and JSON Schema integrations are later beads; this design only needs the native API to be one they can wrap.

## Owner feedback and answers, 2026-10-26 (after gate page v3) — the sugar layer is re-derived
- Owner on v3: "I don't understand the proposed API. The sugar API seems too low level. How might distributed config directives work? How are directives invoked at runtime? What about hierarchical directives — how would a consumer differentiate scopes?"
- Finding (main session): v1 replaced the documented high-level tier — nextgen.md §5 / vil-xlo: "a registration API that invokes registered directive handlers automatically, built on DirectiveDelegator" — with a schema-first `interpret` returning a typed data tree. That was an architect choice never put to the owner. It is withdrawn.
- R26 Distributed directives: "Yes, per module" — each module declares and registers its own directives (name, allowed scopes, arguments, handler); the app passes the list to villanelle; no central schema.
- R27 Invocation: "Load and live changes" — handlers run at load, and again when the config changes while the program runs.
- R28 Hierarchical scopes: a block directive opens a typed scope; directives declare which scopes they may appear in; the handler receives its enclosing scope. (Main-session sketch the owner answered against; the mechanism is the architect's.)
- R29 Inheritance: "Yes, villanelle helps" — villanelle gives scopes one standard way to read a value from the nearest parent that set it.

## Owner gate answers v6, 2026-10-27 (gate/answers-v6; no notes) — current choices, not requirements
- apply: picked A, "The program lists what failed (recommended)": the program reports failed changes via `r.applied(failures)`.
- values: picked A, "The EBNF's rules win (recommended)": no leading zeros, only six escapes; the TS parser changes to match.
- scope: picked C, "B plus first tools": the fixes, `doc` on every declaration, spec/, test kit, PLUS `describe()`, `check()` with exit codes, plugins that hand back directives as data, the rest of spec/ (schema, output layouts, plugin and binding pages, versioned corpus), PLUS `villanelle doc` reference pages and a highlighting grammar.

## Owner gate answers v7, 2026-10-27 (gate/answers-v7)
- R2 clarified: "The “TS config is canonical” was talking about the rasl codebase, not villanelle." (spec note)
- R30 spec/ is canonical in villanelle: "Within villanelle I want the spec to win over a reference language" (spec note, 2026-10-27).
- handles: picked "handles": the program also names the directives it acts on; a change nothing handles is "not applied".
- accept: no pick. Feedback: "I don’t understand the API. “Kind” and “family” and “variant” — how do I know which one to use. Are they different than “directive”s?" The declaration vocabulary is not understood: re-derive before accept.

## Owner in chat, 2026-10-27 (after page v7) — the declaration model and language are reopened
- R31 One concept for what is written: "I just don’t understand why you are trying to make a distinction between directive and settings — are they different somehow? All directives can host scopes with nested directives." No setting/directive split; no family/variant (he did not understand them: "how do I know which one to use").
- R32 Decentralized and recursive directives must both work: "Does that version account for decentralized directives? What about recursive directives?" Prior art to follow: "Go back to the nginx and caddy research: how do we get the power and dynamism and full expressive value from villanelle?"
- R33 A directive takes many values: "Value type directives can have multiple values. Not just “port 8080” but also “port 8080 443 dev tls”".
- R34 Target is option B: this epic closes the escape hatch (a directive reads its own block), reusable blocks with arguments (snippets), and variables. "B is the target."
- R35 Nothing is locked: "We are still trying to define the EBNF and language features. Nothing is locked until I see user APIs that I like." The grammar may change; the page must lead with user APIs (config files and declaration code).

## Owner in chat, 2026-10-27 (after page v8)
- Liked the direction: "I like the direction of this, especially the addition of the variables and snippets. Those were on my wishlist".
- R36 Idiomatic per language: "I don’t love the Python examples, because I feel as though they are too class-inheritance driven and are not making appropriate use of decorators in the right places. Please continue refining the proposal from that direction. The goal is code that is idiomatic to each language." Applies to TypeScript too ("each language").
- Owner, 2026-10-27, on round 9's TypeScript (zod/drizzle/tRPC/Hono references): "The Python reference projects seem reasonable, but the typescript projects all sound like schema builders rather than end1user libraries. What about something like node commander or NestJS as references?" A question and a steer, not a requirement: TS references are re-run against end-user libraries (commander, NestJS).
- Owner, 2026-10-27, minutes later: "those are only two examples from the typescript ecosystem. look for other config libraries/projects to use as inspiration". The commander/NestJS-only run was stopped; a TS ecosystem survey (CLI frameworks, app/plugin frameworks, config and construct-tree projects) now picks the styles to prototype.

## Owner gate answers v9, 2026-10-28 (gate/answers-v9, saved 2026-10-28T03:49Z)
- read: picked "neither". Note, verbatim: "The language bindings are both a bit schizophrenic. They are trying to combine the inspirations rather than choosing one model, and the results are two APIs that are not intuitive. They are close; they are on the right trajectory; but they lack the elegance of a strong API". Steer (not a requirement): each language picks ONE model and follows it all the way; no grafting of several references into one API.
- placement: picked "startup" (recommended): a read from a block that can never hold it fails when the program starts, in both languages. Current choice.
- join: picked "whole" (recommended): a variable is used only as a whole value, never spliced into other text. Current choice.
- Feedback, verbatim: "The idea that typescript “has to be written twice” is problematic." Read as: round 9's claim that TS decorators force each type to be written twice is not accepted as a reason; the TS design must state each type once.
- R19 amended, verbatim: "And third party libraries are ok for things like reflect-metadata". Small runtime support libraries of that kind are allowed; R19's pydantic exclusion (shims stay optional extensions) is unchanged unless he says otherwise.

## Owner in chat, 2026-10-28 (after page v10)
- Verbatim: "These are much closer. I like the direction. But it’s not clear how practical these APIs are for a real integration. But I approve of the language features and design. Should we move forward with the low-level API for now and defer the high-level sugar API for later?" Then "Yes" to the main session's plan (below).
- Approved: the language features and design as of page v10 (directives everywhere, decentralized and recursive, many mixed values, variables as whole values, snippets, own-body escape hatch, include as a first-party extension).
- Plan he said yes to (main session's proposal, not his words): (1) the low-level API (R15 tiers 1-2: tokens/parse tree and the directive layer) is designed and built next; (2) it must carry what the sugar needs: located errors, a stable identity per written place, the change list, include as a file graph, variables and snippets expanded with each value traceable to where it was written; (3) design rule: the round-10 sugar (final-py dataclasses, final-ts NestJS) must be buildable purely on top of it, checked by a reviewer before the gate; (4) done = rasl loads family_room.conf and hyperhdr.conf through the low-level API in Python and TypeScript.
- Deferred with the sugar (vil-xlo): pyholds, tsread, @OnChange vs applied(failures), and the startup check for wrong-block reads (needs declared directives).
