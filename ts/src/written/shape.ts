/**
 * The text-alone shape of a statement (round 12 slices.md 2.3): which kind a directive node is, and the one
 * problem that makes a `@set`, `@snippet` or `@use` line unreadable by its text alone. The one home of these shape
 * rules: the document classifies its statements with it, the edit checks use it, and the binding's walk reports
 * the same codes at the same places. Private to the package.
 */

import { isWordKind } from "../syntax/tokens.js";
import { anatomyOf, type IDirectiveAnatomy } from "../anatomy.js";
import type { SourceSpan } from "../gen/api/shared.js";
import type { Node, Token } from "../gen/api/syntax.js";
import { DiagnosticCode } from "../gen/api/codes.js";
import { NodeKind, StatementKind, statementOfKeyword, TokenKind } from "../gen/api/kinds.js";

/** A statement's kind by its text alone: one of the generated statement kind list. */
export type ShapeKind = StatementKind;

/** One problem of a line's text alone. */
export interface IShapeFault {
  readonly code: DiagnosticCode;
  readonly span: SourceSpan;
  /** The detail PR 3's message carried (`$a`, a snippet name), if any. */
  readonly detail?: string;
}

/** What a directive or error node is, by its text alone, before any per-block rule. */
export interface IShape {
  readonly kind: ShapeKind;
  /**
 * Why a `@set`, `@snippet` or `@use` line, or an `@name` no extension owns, is unreadable; undefined otherwise (and
 * for a syntax error node).
 */
  readonly fault: IShapeFault | undefined;
  /** A `set`'s variable name, or a snippet's name (for the one-per-block rules). */
  readonly claims: string | undefined;
}

/** The shape of one node of a block, ignoring the one-per-block rules (E5002, E5005). */
export function shapeOf(tokens: readonly Token[], node: Node, extensions: ReadonlySet<string>): IShape {
  if (node.kind !== NodeKind.Directive) return { kind: "unreadable", fault: undefined, claims: undefined };
  return shapeOfAnatomy(tokens, anatomyOf(tokens, node), extensions);
}

/**
 * The shape of a directive by its anatomy, ignoring the one-per-block rules (the binding's walk asks this too). The
 * head's token kind decides (spec 2.5): a WORD is a directive whatever its text; an AT_WORD is `@set`, `@snippet`,
 * `@use`, an extension line (`@` and a registered extension's name), or else an unreadable line (E3008, which is no
 * text-alone rule: it depends on the registered extensions, so `isTextAlone` leaves it out).
 */
export function shapeOfAnatomy(tokens: readonly Token[], anatomy: IDirectiveAnatomy, extensions: ReadonlySet<string>): IShape {
  const name = tokens[anatomy.name];
  if (name === undefined) throw new Error("a directive node has no name token");
  if (name.kind !== TokenKind.AT_WORD) return { kind: "directive", fault: undefined, claims: undefined };
  const [first, ...rest] = anatomy.values;
  const firstToken = typeof first === "number" ? tokens[first] : undefined;
  switch (statementOfKeyword(name.text.slice(1))) {
    case StatementKind.Set: {
      if (firstToken?.kind !== TokenKind.VARIABLE || rest.length === 0 || anatomy.block !== undefined) {
        return { kind: "unreadable", fault: { code: DiagnosticCode.BadSet, span: name.span }, claims: undefined };
      }
      return { kind: "set", fault: undefined, claims: firstToken.text.slice(1) };
    }
    case StatementKind.Snippet: {
      const params: string[] = [];
      const bad = { kind: "unreadable", fault: { code: DiagnosticCode.BadSnippet, span: name.span }, claims: undefined } as const;
      for (const ref of rest) {
        const token = typeof ref === "number" ? tokens[ref] : undefined;
        if (token?.kind !== TokenKind.VARIABLE || params.includes(token.text.slice(1))) return bad;
        params.push(token.text.slice(1));
      }
      if (firstToken === undefined || !isWordKind(firstToken.kind) || anatomy.block === undefined) return bad;
      return { kind: "snippet", fault: undefined, claims: firstToken.text };
    }
    case StatementKind.Use:
      if (firstToken === undefined || !isWordKind(firstToken.kind) || anatomy.block !== undefined) {
        return { kind: "unreadable", fault: { code: DiagnosticCode.BadUse, span: name.span }, claims: undefined };
      }
      return { kind: "use", fault: undefined, claims: undefined };
    default:
      if (extensions.has(name.text.slice(1))) return { kind: "extension", fault: undefined, claims: undefined };
      return { kind: "unreadable", fault: { code: DiagnosticCode.UnknownExtension, span: name.span, detail: name.text }, claims: undefined };
  }
}

/** Whether a fault is one of the text-alone rules an edit refuses (E5002, E5005, E5009 to E5011; spec 2.8). */
export function isTextAlone(fault: IShapeFault): boolean {
  return fault.code !== DiagnosticCode.UnknownExtension;
}

/** A snippet line's parameter tokens (VARIABLE token indices), in order. Call only on a well-formed snippet. */
export function parameterTokens(tokens: readonly Token[], node: Node): readonly number[] {
  const [, ...rest] = anatomyOf(tokens, node).values;
  return rest.filter((ref): ref is number => typeof ref === "number");
}

/**
 * The shapes of a block's nodes in order, with the one-per-block rules applied: a second `set` of a name is
 * unreadable (E5002 at its `$name`), a second `snippet` of a name too (E5005 at its name). `claimed` holds names a
 * block already binds (a snippet body's parameters).
 */
export function blockShapes(
  tokens: readonly Token[],
  nodes: readonly Node[],
  extensions: ReadonlySet<string>,
  claimed: Iterable<string> = [],
): IShape[] {
  const sets = new Set(claimed);
  const snippets = new Set<string>();
  return nodes.map((node) => {
    const shape = shapeOf(tokens, node, extensions);
    if (shape.kind === StatementKind.Set && shape.claims !== undefined) {
      if (sets.has(shape.claims)) {
        const variable = tokens[anatomyOf(tokens, node).values[0] as number];
        const span = variable?.span ?? (tokens[node.start] as Token).span;
        return { kind: "unreadable", fault: { code: DiagnosticCode.VariableSetTwice, span, detail: variable?.text ?? "" }, claims: undefined };
      }
      sets.add(shape.claims);
    }
    if (shape.kind === StatementKind.Snippet && shape.claims !== undefined) {
      if (snippets.has(shape.claims)) {
        const nameToken = tokens[anatomyOf(tokens, node).values[0] as number];
        const span = nameToken?.span ?? (tokens[node.start] as Token).span;
        return { kind: "unreadable", fault: { code: DiagnosticCode.SnippetDefinedTwice, span, detail: shape.claims }, claims: undefined };
      }
      snippets.add(shape.claims);
    }
    return shape;
  });
}

/** The statement nodes of a document or block node: its directive and error children. */
export function statementNodes(container: Node): readonly Node[] {
  return container.children.filter((child) => child.kind === NodeKind.Directive || child.kind === NodeKind.Error);
}
