/**
 * The types carry the kinds (frozen-m2.md sections 1 to 3; spec 2.10). Compile time (`pnpm typecheck`): each union's
 * `kind` is exactly its generated kind list, and each member section 2 marks absent does not compile on that variant
 * (`@ts-expect-error`, which fails the typecheck if the line compiles). Run time: the same members are absent from
 * the real objects, and narrowing by `kind` is all a program needs (no casts).
 */

import { describe, expect, it } from "vitest";

import type {
  Change,
  ChangeKind,
  ExpandedValue,
  IDiagnostic,
  INode,
  IOverride,
  IPlace,
  IStep,
  IToken,
  IUnreadableExpansion,
  NodeKind,
  PlaceKind,
  Statement,
  StatementKind,
  StepKind,
  TokenKind,
  UnreadableReason,
  ValueKind,
  Variable,
  VariableKind,
  WrittenValue,
} from "./index.js";
import { include } from "./include.js";
import { render } from "./rendered/render.js";
import { memorySource } from "./source.js";
import { villanelle } from "./written/index.js";
import { type ConfigText, quote, text } from "./text.js";

/** True exactly when A and B are the same type. */
type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;
function assertType<T extends true>(): T | undefined {
  return undefined;
}

// Each union's kind is its whole list (less `except`), and nothing else.
assertType<Equal<Statement["kind"], StatementKind>>();
assertType<Equal<WrittenValue["kind"], ValueKind>>();
assertType<Equal<Variable["kind"], VariableKind>>();
assertType<Equal<ExpandedValue["kind"], Exclude<ValueKind, "reference">>>();
assertType<Equal<Change["kind"], ChangeKind>>();
assertType<Equal<IStep["kind"], StepKind>>();
assertType<Equal<(IPlace | IOverride)["kind"], PlaceKind>>();
assertType<Equal<IUnreadableExpansion["reason"], UnreadableReason>>();
assertType<Equal<INode["kind"], NodeKind>>();
assertType<Equal<IToken["kind"], TokenKind>>();
// The generated lists are string-literal types: a literal narrows without an import.
assertType<Equal<StatementKind, "directive" | "extension" | "set" | "snippet" | "use" | "unreadable">>();
assertType<Equal<IDiagnostic["code"] extends string ? true : false, true>>();
// Milestone 5: `COLON` is gone from the token kinds (frozen-m5.md B), `~` and `@name` came.
assertType<Equal<Extract<TokenKind, "COLON">, never>>();
assertType<Equal<Extract<TokenKind, "TILDE" | "AT_WORD">, "TILDE" | "AT_WORD">>();
// Config text (spec 6.9): a branded string, made by quote() and text() only; a plain string is not one.
assertType<Equal<ConfigText extends string ? true : false, true>>();
assertType<Equal<string extends ConfigText ? true : false, false>>();
assertType<Equal<ReturnType<typeof quote>, ConfigText>>();
assertType<Equal<ReturnType<typeof text>, ConfigText>>();

const MAIN = `@set $n 3;
@snippet s $p {
    y $p;
}
@use s 1;
@include "part.conf";
x "a" [1, 2] c[0~$n] c[$n];
oops ] ;
`;

async function loaded(): Promise<{ statements: readonly Statement[]; graph: Awaited<ReturnType<ReturnType<typeof villanelle>["load"]>> }> {
  const graph = await villanelle({ source: memorySource({ "main.conf": MAIN, "part.conf": "" }), extensions: [include()] }).load("main.conf", {
    overrides: { o: text("1") },
  });
  return { statements: graph.root.block.statements, graph };
}

function kindOf<K extends Statement["kind"]>(statements: readonly Statement[], kind: K): Extract<Statement, { kind: K }> {
  const found = statements.find((s): s is Extract<Statement, { kind: K }> => s.kind === kind);
  if (found === undefined) throw new Error(`no ${kind} statement`);
  return found;
}

describe("members exist only on the variants where they can succeed (section 2)", () => {
  it("statements", async () => {
    const { statements } = await loaded();
    const directive = kindOf(statements, "directive");
    const extension = kindOf(statements, "extension");
    const set = kindOf(statements, "set");
    const snippet = kindOf(statements, "snippet");
    const use = kindOf(statements, "use");
    const unreadable = kindOf(statements, "unreadable");
    expect([directive.name, extension.name, snippet.name, use.snippetName]).toEqual(["x", "include", "s", "s"]);

    // @ts-expect-error an extension line has no rename
    expect(extension.rename).toBeUndefined();
    // @ts-expect-error a set line has no name
    expect(set.name).toBeUndefined();
    // @ts-expect-error a set line has no block
    expect(set.block).toBeUndefined();
    // @ts-expect-error a set line has no rename
    expect(set.rename).toBeUndefined();
    // @ts-expect-error a snippet line has no values
    expect(snippet.values).toBeUndefined();
    // @ts-expect-error a snippet line has no set
    expect(snippet.set).toBeUndefined();
    // @ts-expect-error a use line has no name
    expect(use.name).toBeUndefined();
    // @ts-expect-error a use line has no block
    expect(use.block).toBeUndefined();
    // @ts-expect-error an unreadable line has no values
    expect(unreadable.values).toBeUndefined();
    // @ts-expect-error an unreadable line has no set
    expect(unreadable.set).toBeUndefined();
    // @ts-expect-error a directive has no variable
    expect(directive.variable).toBeUndefined();
    // @ts-expect-error a directive has no parameters
    expect(directive.parameters).toBeUndefined();
    for (const s of statements) {
      expect(typeof s.insertBefore).toBe("function");
      expect(typeof s.insertAfter).toBe("function");
    }
  });

  it("variables", async () => {
    const { statements, graph } = await loaded();
    const parameter = kindOf(statements, "snippet").parameters[0];
    const override = graph.variables("o")[0];
    if (parameter === undefined || override?.kind !== "override") throw new Error("no parameter or override");
    const set = kindOf(statements, "set").variable;
    expect([set.kind, parameter.kind, override.kind]).toEqual(["set", "parameter", "override"]);
    expect(typeof set.set).toBe("function");

    // @ts-expect-error a parameter has no set (edit the use line)
    expect(parameter.set).toBeUndefined();
    // @ts-expect-error an override has no place
    expect(override.place).toBeUndefined();
    // @ts-expect-error an override has no line
    expect(override.line).toBeUndefined();
    // @ts-expect-error an override has no rename (use setOverride)
    expect(override.rename).toBeUndefined();
    // @ts-expect-error an override has no set (use setOverride)
    expect(override.set).toBeUndefined();
  });

  it("written values and expanded values", async () => {
    const { statements, graph } = await loaded();
    const [str, list, slice, index] = kindOf(statements, "directive").values;
    if (str?.kind !== "string" || list?.kind !== "list" || slice?.kind !== "slice" || index?.kind !== "index") throw new Error("kinds");
    expect(list.items.map((v) => v.text)).toEqual(["1", "2"]);
    expect([slice.name.kind, slice.name.text, index.name.kind, index.name.text]).toEqual(["word", "c", "word", "c"]);
    // @ts-expect-error a string has no items
    expect(str.items).toBeUndefined();
    // @ts-expect-error a list has no name
    expect(list.name).toBeUndefined();

    const x = render(graph).block.find((d) => d.name === "x");
    const [a, l, s, i] = x?.values ?? [];
    if (a?.kind !== "string" || l?.kind !== "list" || s?.kind !== "slice" || i?.kind !== "index") throw new Error("expanded kinds");
    expect(l.items.map((v) => v.integer())).toEqual([1, 2]);
    expect(l.items[0]?.written.text).toBe("1");
    expect([s.name, s.start, s.end, i.name, i.index]).toEqual(["c", 0, 3, "c", 3]);
    // @ts-expect-error an expanded string has no items
    expect(a.items).toBeUndefined();
    // @ts-expect-error an expanded slice has no index
    expect(s.index).toBeUndefined();
    // @ts-expect-error an expanded index has no start
    expect(i.start).toBeUndefined();
    const expanded: ExpandedValue = l;
    expect(expanded.kind).toBe("list");
  });

  it("every edit and override takes config text: a plain string is a type error (spec 6.9, milestone 5)", async () => {
    const { statements, graph } = await loaded();
    const directive = kindOf(statements, "directive");
    // @ts-expect-error a plain string is not config text
    expect(() => directive.set("8080")).not.toThrow();
    directive.set(text("8080"));
    directive.set(quote("web"));
    const [value] = directive.values;
    // @ts-expect-error a value's set takes config text
    value?.set("1");
    // @ts-expect-error a value's replaceWithText takes config text
    value?.replaceWithText("1");
    // @ts-expect-error insertStatements takes config text
    graph.root.block.insertStatements(0, "a;");
    // @ts-expect-error setOverride takes config text
    graph.setOverride("o", "2");
    const overrides: ReadonlyMap<string, ConfigText> = graph.overrides;
    expect([...overrides.keys()]).toEqual(["o"]);
  });

  it("a value's set keeps the handle and changes its kind (spec 6.1, milestone 5)", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "@set $p 2284;\nmax_count $p;\n" }) }).load("main.conf");
    const directive = kindOf(graph.root.block.statements, "directive");
    const value = directive.values[0];
    if (value?.kind !== "reference") throw new Error("not a reference");
    expect(value.name).toBe("p");
    value.set(text("2400"));
    // `value` was narrowed before the edit and is stale after it: a program reads it again and narrows again.
    const after = directive.values[0];
    expect(after).toBe(value);
    expect(after?.kind).toBe("word");
    expect(after?.text).toBe("2400");
    expect("name" in value).toBe(false);
    after?.set(text("[1, $p]"));
    const list = directive.values[0];
    expect(list).toBe(value);
    if (list?.kind !== "list") throw new Error("not a list");
    expect(list.items.map((item) => item.kind)).toEqual(["word", "reference"]);
    expect(graph.root.text).toBe("@set $p 2284;\nmax_count [1, $p];\n");
  });
});
