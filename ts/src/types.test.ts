/**
 * The types carry the kinds (frozen-m2.md sections 1 to 3; spec 2.10). Compile time (`pnpm typecheck`): each union's
 * `kind` is exactly its generated kind list, and each member section 2 marks absent does not compile on that variant
 * (`@ts-expect-error`, which fails the typecheck if the line compiles). Run time: the same members are absent from
 * the real objects, and narrowing by `kind` is all a program needs (no casts).
 */

import { describe, expect, it } from "vitest";

import * as browserModule from "./browser.js";
import type { BrowserFunctions, IoFunctions, NodeFunctions } from "./gen/api/io.js";
import type { RenderedFunctions } from "./gen/api/rendered.js";
import type { DiagnosticsConstructor, SharedFunctions } from "./gen/api/shared.js";
import type { SyntaxFunctions } from "./gen/api/syntax.js";
import type { IncludeFunctions, WrittenFunctions } from "./gen/api/written.js";
import * as includeModule from "./include.js";
import * as rootModule from "./index.js";
import * as nodeModule from "./node.js";
import * as renderedModule from "./rendered/index.js";
import * as syntaxModule from "./syntax/index.js";
import * as writtenModule from "./written/index.js";
import type { Diagnostic, Override, Place, Step, PlaceKind, StepKind } from "./index.js";
import { include } from "./include.js";
import { render } from "./rendered/render.js";
import { knobly } from "./written/index.js";
import { type ConfigText, memorySource, quote, text } from "./index.js";
import type { Change, ChangeKind } from "./rendered/index.js";
import type { Node, NodeKind, Token, TokenKind } from "./syntax/index.js";
import type { ExpandedValue, Statement, StatementKind, UnreadableExpansion, UnreadableReason, ValueKind, Variable, VariableKind, WrittenValue } from "./written/index.js";

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
assertType<Equal<Step["kind"], StepKind>>();
assertType<Equal<(Place | Override)["kind"], PlaceKind>>();
assertType<Equal<UnreadableExpansion["reason"], UnreadableReason>>();
assertType<Equal<Node["kind"], NodeKind>>();
assertType<Equal<Token["kind"], TokenKind>>();
// The generated lists are string-literal types: a literal narrows without an import.
assertType<Equal<StatementKind, "directive" | "extension" | "set" | "snippet" | "use" | "unreadable">>();
assertType<Equal<Diagnostic["code"] extends string ? true : false, true>>();
// Milestone 5: `COLON` is gone from the token kinds (frozen-m5.md B), `~` and `@name` came.
assertType<Equal<Extract<TokenKind, "COLON">, never>>();
assertType<Equal<Extract<TokenKind, "TILDE" | "AT_WORD">, "TILDE" | "AT_WORD">>();
// Config text (spec 6.9): a branded string, made by quote() and text() only; a plain string is not one.
assertType<Equal<ConfigText extends string ? true : false, true>>();
assertType<Equal<string extends ConfigText ? true : false, false>>();
assertType<Equal<ReturnType<typeof quote>, ConfigText>>();
assertType<Equal<ReturnType<typeof text>, ConfigText>>();

// Each import path's free functions have the generated signatures (spec/codegen.md section 4: `<Module>Functions`),
// and each class a program constructs has its constructor's (`<Class>Constructor`).
const FREE_FUNCTIONS: readonly [
  SharedFunctions & IoFunctions,
  SyntaxFunctions,
  WrittenFunctions,
  RenderedFunctions,
  BrowserFunctions,
  NodeFunctions,
  IncludeFunctions,
] = [rootModule, syntaxModule, writtenModule, renderedModule, browserModule, nodeModule, includeModule];
const CONSTRUCTORS: readonly [DiagnosticsConstructor] = [rootModule.Diagnostics];

const MAIN = `@set $n 3;
@snippet s $p {
    y $p;
}
@use s 1;
@include "part.conf";
x "a" [1, 2] c[0~$n] c[$n];
oops ] ;
`;

async function loaded(): Promise<{ statements: readonly Statement[]; graph: Awaited<ReturnType<ReturnType<typeof knobly>["load"]>> }> {
  const graph = await knobly({ source: memorySource({ "main.conf": MAIN, "part.conf": "" }), extensions: [include()] }).load("main.conf", {
    overrides: { o: text("1") },
  });
  return { statements: [...graph.root.block], graph };
}

function kindOf<K extends Statement["kind"]>(statements: readonly Statement[], kind: K): Extract<Statement, { kind: K }> {
  const found = statements.find((s): s is Extract<Statement, { kind: K }> => s.kind === kind);
  if (found === undefined) throw new Error(`no ${kind} statement`);
  return found;
}

describe("each import path's free functions (spec/codegen.md section 4)", () => {
  it("match the generated interfaces (checked at compile time by FREE_FUNCTIONS' declared type)", () => {
    expect(FREE_FUNCTIONS).toHaveLength(7);
    expect(CONSTRUCTORS).toHaveLength(1);
  });
});

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

    const x = [...render(graph).block].find((d) => d.name === "x");
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
    const graph = await knobly({ source: memorySource({ "main.conf": "@set $p 2284;\nmax_count $p;\n" }) }).load("main.conf");
    const directive = kindOf([...graph.root.block], "directive");
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
