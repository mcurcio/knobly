# Round 11 design review (design-reviewer; saved by the main session from its result)

Note: the revise step did not see this review (the reviewer cannot write files). The build's code architect weighs it.

Review of the round 11 low-level API design. Mode: design mode, system layer (R15 tiers 1-2). The villanelle repo has no `.claude/gates.json` and its CLAUDE.md lists no standards, so I reviewed against the brief, requirements.md (R1-R36), beads vil-9ze and vil-stq, and the owner-design vocabulary.

**Verdict: FAIL.** The main split is sound and I would keep it: Syntax, load, Directive/Arg, Origin, Address, diff, Extension. On top of it, five integrations type-check, and the rasl reader that replaces about 724 lines of loader.py and connect_parser.py is 255 lines. But all five integrators hit the same three problems, each from their own direction. That pattern means the model is missing three concepts. These are not small fixes, and they are what must change.

**Required artifacts**
- The domain model is present (§5, with an owns / not-its-job table).
- The interfaces are present in both languages. Their gaps are covered under findings below.
- The tracer bullet is present but does not reach every layer (finding 6).
- Design-it-twice is done for three sub-questions (key rule, synchronous Python load, the delegator). The core model gets one-line mentions only (§4). See finding 8.
- Costs and a new-terms table are present. The table is incomplete (finding 9).
- Nothing required is missing outright, so this is not an automatic fail.

## Findings, most severe first

### 1. The partial tree and diff cannot tell "removed" from "unreadable"
- **Rule:** one concept, one domain; source of truth.
- **Where:** index.d.ts:281 and __init__.pyi:271 say lines with syntax errors are left out of `Loaded.body`. diff then compares by address, so a missing line shows up as removed.
- **What the integrators did:** integrate-rasl-py/rasl_vl/reload.py:29-32 refuses the whole reload, because a half-typed file would strip a property from a running node. integrate-rasl-ts/src/source.ts:47 rejects any load that has diagnostics.
- **Unspecified:** what an expansion failure leaves behind. In the planted `max_count $pixel` (integrate-rasl-ts/planted/family_room.bad.conf), rasl's property rule would read a valueless `max_count;` as `true`.
- **Why it matters:** "Loaded is always a whole result" (index.d.ts:279) is false for diff's purposes. The tree's missing parts are being used as the signal for a different concept, the removal of a directive. R6 asks for partial trees, but here that buys reload nothing. rasl wants to hold back only the affected node, and cannot.
- **Fix, at the right level:** the domain must say what each directive's state is: read, unreadable, or failed expansion. diff must report "unknown" as its own outcome, never as Removed. Which mechanism does that is for the code architect.

### 2. Problems have no place to collect: three ways to make one and no sink
- **Rule:** prior art (the design's own chosen model); R14 not carried.
- **Three ways today:**
  - load collects its own (`loaded.diagnostics`);
  - readers and `error()` throw a DiagnosticError;
  - programs build a Diagnostic by hand.
- **What every consumer wrote:**
  - a collector: rasl-py reader.py:282-298 (it had to be a class because of how pyright treats `@contextmanager`); rasl-ts errors.ts:5 (`collect`);
  - `.error(...).diagnostic` without ever throwing: rasl-py validate.py:33,39; third-party py/vlschema.py:78,123,129 and ts/vlschema.ts:69,120.
- **A requirement dropped without saying so:** R14 (vil-bzv) asks for a "report(directive, message, code?) helper". The design never mentions it.
- **A cost understated:** §8 lists the "try per node" cost for TypeScript only. Python pays it too: design §3 itself uses a try/except per node, and so does rasl-py.
- **Prior art:** PostCSS, the model §4 picks, has exactly this half: `Result.messages`, `result.warn()` and `node.warn(result, …)`. HCL returns `hcl.Diagnostics` from every decode rather than raising.
- **Fix:** collecting diagnostics is its own concept: one sink that load, readers and programs all report into. Throwing should be one way to reach it, not the only one.

### 3. The file is not a node of the tree, and the root file is read by a different path
- **Rule:** prior art; one model; ownership split.
- **The file is a different kind from a block.** `Loaded` has no origin and no `error()`. All five integrations built a fake zero-width place at 0:0 of the root file by hand:
  - rasl-py reader.py:312-316;
  - rasl-ts errors.ts:28;
  - sugar-py _build.py:309-316;
  - third-party py/vlschema.py:133-135 and ts/vlschema.ts:125-128. Its probe prints `proxy-bad.conf:1:1: vlschema/missing: listen` with an empty caret on a comment line.
- **TypeScript has to guess the type by shape:** ts/vlschema.ts:50 uses `!("name" in target)`.
- **Two ways to read files:** the root comes in as a Document the program read itself, while includes go through the include extension's loader:
  - rasl-py reader.py:38 against files.py:11-27;
  - rasl-ts source.ts:43 against :60. A missing root file becomes a bare string, not a Diagnostic (:44);
  - sugar-ts app.ts:494-498 calls the loader by hand with `parentPath: ""`.
- **Prior art departed from:** in PostCSS, `Root` is a Container node with `source` and `error()`. In Python's ast, `Module` is an ordinary node.
- **Ownership split:** load owns the file graph (depth, cycles, R21) but not where files come from, which the include extension owns.
- **"Read once" is a convention, not a guarantee:** R21 quotes the owner, "Obviously the file only needs to be read once". But the loader contract (include.d.ts:16, include.pyi:15) returns the source on every call, so a file included at two places is read twice unless every program's loader caches. index.d.ts:255 says "Read and parsed once", which is true only of parsing.
- **Fix:** model each document, root or included, as a node of the same tree. Make "where files come from" a port that load owns, used by the root and by include alike.

### 4. The change list compares text, and `whole` fits no real consumer
- **Rules:** deletion test; one concept, one domain; a design claim that is false.
- **Text is not value.** `Arg.text` is "exactly as written, quotes included" and is what "changed" compares (index.d.ts:170). A list's text includes its comments and line breaks. `xmas_light_colors` in configs/family_room.v10.conf:37-43 has a commented-out line inside the list, so editing that comment restarts the node (rasl-ts friction 7). §8 lists only the `0.5`/`0.50` case. Both sugars rebuilt value equality themselves:
  - sugar-ts app.ts:579 compares printed values;
  - sugar-py _changes.py:150 says `prev == rec  # touched by text, same value`.
  Two copies of the same logic in two consumers means core is missing that piece.
- **The meaning of text is unspecified.** For `max_count $pixels`, is `text` `$pixels` or `2284` (rasl-py friction 8)?
- **`whole` fails the deletion test.**
  - None of the four programs that use diff passes `whole`. I grepped all four.
  - rasl needs retune, rewire and restart told apart (rasl-py reload.py:13-24, rasl-ts reload.ts:6-31), and `whole` merges them into one Replaced.
  - Both sugars show that §7's row "restart=True → whole" is wrong: restart applies per line, and other changes inside stay Changed (sugar-py _changes.py:129-131, sugar-ts app.ts:544-562).
  - It is undefined which kind comes back when `whole` is on and the directive's own values changed.
- **Every consumer groups changes by unit itself:**
  - rasl-py reload.py:81-106 walks parents and subtrees;
  - rasl-ts reload.ts:15 groups by position, tied to the depth its own key rule produces;
  - sugar-py _changes.py:105-136 builds the ancestors and walks the subtrees;
  - sugar-ts app.ts:552-559 bubbles changes up.
- **§6 states rasl's needs wrongly:** "one restart of leds" is not what rasl does.
- **Fix:** "changed" must mean the value changed, with comments and other non-value text excluded. Changes must be groupable by the unit the program thinks in, such as a node. Remove `whole` and `Replaced` unless some consumer needs them.

### 5. The design's sugar table is false in three rows, and one sugar silently loses changes
- **Rule:** the brief's design rule, "the round-10 sugar must be buildable purely on top of this API".
- **Inherited values (R29):**
  - Changing a block's `fps` changes every node that inherits it, but diff lists only `graph › fps`.
  - sugar-ts records which handler read which value itself (app.ts:518-568, 637-664).
  - sugar-py does not, and loses the change. My probe (scratchpad inherit_probe.py, run against sugar-py's fake core) changed `fps 20hz` to `fps 30hz` in `graph`. Output: `v2 value: leds fps 30hz`, `v2 value: hsl fps 30hz`, then `changes.of(Node): []`.
  - So "`parent` is enough for inheriting" is true for reading values and false for change lists.
- **applied(failures):** "diff keyed by address (the sugar keeps the last applied load)" is false. After a failed change, what runs is not any one Loaded. Both sugars keep their own snapshot plus a pending set (sugar-py _changes.py:88-97 and 168-205; sugar-ts app.ts:254-256 and 590-598). rasl-ts source.ts:54 even saves the accepted load before it has been applied.
- **restart → whole:** see finding 4.
- **Fix:** the page must either own these in this layer, or say plainly that the sugar keeps its own record of values, what each handler read, and what is pending. Today it claims they are covered.

### 6. The tracer bullet skips the include extension
- **Rule:** a tracer bullet must cross every layer.
- **Where:** §8 says the bullet loads family_room and hyperhdr. A grep shows `include` appears 0 times in every config across all five integrations.
- **Untested as a result:** the include extension, the include file graph, the new Python include graph (C7, called the biggest new code in §8's "Scope moves"), and handed-in variables.
- **Fix:** the bullet must load a file that includes another file (at least once at two places, for R21) and that uses a handed-in variable.

### 7. A rule the owner never stated, which blocks rasl's real need
- **Rule:** trace every invariant to the owner.
- **Where:** §6's 5xxx list makes "`set` of a handed-in name" an error. No owner quote exists for it: requirements.md and briefing-v10 have nothing, and briefing-v9:26 only says `$host` is handed in.
- **Cost:** rasl cannot write `set $leds_host "10.0.60.30";` in the file and let `rasl --set` override it (rasl-ts friction 10), so it did not use handed-in variables at all.
- **Prior art:** Make, Terraform's `-var` over a variable's default, and Helm's `--set` over values.yaml all let the command line win over a default in the file.
- **Fix:** ask the owner, and drop the rule unless he confirms it.

### 8. The guarantees the design claims are conventions
- **Rule:** guarantees, strongest first; separate what is structurally guaranteed from what is merely true today.
- **"Typed in TS, checked when made in Python" (§6) does not stop collisions with villanelle's codes:**
  - Python's `Diagnostic` is a public, unchecked dataclass (__init__.pyi:111-116).
  - In TypeScript, `Diagnostic` is a plain interface whose code type accepts `` `E${number}` ``. sugar-ts invents E6001 and up with `satisfies Record<string, DiagnosticCode>` (app.ts:42-58).
  - The two sugars picked different schemes (`vl/…` against E6xxx), which already breaks R17 (identical codes in both languages) at tier 3.
- **"Located, or not a problem" (§7 rule 3) is not true:**
  - `Origin.written` may be `Handed`, which has no location. rasl-ts errors.ts:35 falls back to `via[0]`.
  - `Directive.origin` has the same wide type, although a directive's name can never be handed in (rasl-py reader.py:307).
- **Python lets two loads use different key rules:** key and extensions are passed on every `load` call (__init__.pyi:287-293). Two loads with different key rules are caught only at diff (ValueError, :338), and "how Python checks" is parked. TypeScript ties them to one processor.
- **Weak alternative:** design-it-twice never weighed HCL's way of returning diagnostics, which is exactly where findings 2 and 3 landed.
- **Fix:** each claim must be backed by the structure, or restated as a convention.

### 9. Interfaces missing invariants or ordering rules
- **Rule:** a signature alone is not a contract.
- **The key rule (index.d.ts:244, __init__.pyi:225):**
  - It does not say which fields of `parent` exist when it runs. All four integrations that walk up from it read `parent.name`, and sugar-ts caches by parent object (app.ts:342-366).
  - It does not say whether `args` are already expanded.
  - It cannot see whether the directive has a block (rasl-py friction 12, rasl-ts friction 6).
  - Both sugars re-walk the whole parent chain on every call (sugar-py _key.py:67-88).
- **`plain()`** does not say what a quoted `"8080"` becomes (rasl-py friction 7, third-party F4).
- **`Address`:**
  - Its string form is unspecified, and Python has no `text` at all (TypeScript has :214), though §5 shows `graph › node hue_ramp › connect #1`.
  - It has no `parent`.
- **Handed-in variable text** is "read by the value rule" (index.d.ts:339), with no error mode for text containing `;` or `{`.

### 10. Names
- **Rule:** concepts and the new-terms table.
- **`node`:** requirements.md:41 already names the "node" clash (tier-1 node, file-graph node, rasl's `node` directive). The design still adds `Directive.node` and `DocumentNode`, and rasl-ts reads `spec.directive.node` (friction 11).
- **`graph`:** `loaded.graph` against rasl's `graph` block is also unresolved.
- **`Processor`** is a new term missing from the new-terms table.
- **`Directive`** clashes with the sugar's `@Directive` decorator (sugar-ts friction 13).

### 11. Smaller points
- `body or ()` is written 7 times in rasl_vl. need() and noMore() are called 17 times in read.ts.
- No "first child named X" helper: rasl-py reader.py:125 and :251; design rasl.ts:118.
- There is no limits option, so round 10's `maxDepth` knob cannot be honoured (sugar-ts friction 11).
- If the delegator answer is A, the vil-stq.3 and vil-stq.4 bead titles, which still say "delegator", need rewording.

## What I attacked that held up
- **The split itself:** origin separate from address (§7 rule 2), expansion done once in load, read-only directives, include as an extension (R20). Third-party says `origin.via` came through `arg.error()` with no extension code, and the probes print the use line and the definition correctly in both languages.
- **One model per language (R36):** the Python design follows `ast` (match, `__match_args__`, a `walk` function, synchronous). TypeScript follows PostCSS (a processor, methods, async). Neither mixes several references, which answers the owner's v9 note.
- **Practicality:** the rasl readers are 255 lines in Python and 145 in TypeScript (non-blank, non-comment), replacing 1,125 raw lines across loader.py, connect_parser.py and rasl.ts. The pydantic and zod extensions are about 110 and 102 lines. The boilerplate is real but small, apart from findings 2-4.
- **The delegator question:** R11 is bead text, not owner words, so treating it as revisable is correct.
- **Shared-factory defaults:** not applicable, because the design adds no new default to an existing factory.

## Must change before PASS
1. Give each directive a state (read, unreadable, failed expansion), and make diff report "unknown", not Removed.
2. Give diagnostics one collecting sink, which also delivers R14's report helper.
3. Make the document (root or included) a node of the tree with an origin and `error()`, and make the file source a port that load owns, used by the root and by include. Guarantee R21's "read once" structurally.
4. Define "changed" by value, not text, with comments excluded. Let changes be grouped by the unit the program thinks in, and remove `whole` and `Replaced` unless a consumer is shown to need them.
5. Correct §7's sugar table: inherited reads, applied(failures), restart.
6. Make the tracer bullet cross include and handed-in variables.
7. Trace or drop the rule against `set` of a handed-in name.
8. Back the code-namespace and "every diagnostic is located" claims with structure, or restate them. Reserve a code band for the sugar.
9. Specify the key rule's contract (ordering and what it receives), `plain()` per kind, and `Address`'s string form and parent, the same in both languages.
10. Resolve the `node` and `graph` name clashes, and add `Processor` to the new-terms table.

**FAIL**: items 1-4 are changes to the model and must land before the gate; items 5-10 are corrections to the page.

## Reviewer friction
- The workflow told me to write review.md, but this reviewer never writes files. The full review is in summary for the caller to save.
- Rerunning the checks had side effects. round11/run.sh rewrites the evidence files in api-ts/evidence and api-py/evidence, and I ran it before reading it. I ran every later check directly to the screen instead. The Python runs also created __pycache__ folders in sugar-on-top-py. Better rerun scripts would print to the screen and not delete evidence first.
- In zsh, `$RUN` with spaces in it is not split into words, so the uv commands failed with exit 127 until I wrapped them in bash -c. The run scripts already use bash.
- Nothing in any integration actually runs: there is no v10 parser. Only sugar-py runs, against its hand-written fake core. My inherited-change probe therefore tested sugar-py on that fake, not on a real load.
