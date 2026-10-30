/**
 * The adapter: the only module that touches the ANTLR runtime and the generated parser (src/gen/, made by
 * tools/gen.sh). Everything it returns is ours: Token, Node, Diagnostic.
 */

import { CharStreams, CommonTokenStream } from "antlr4";

import { makeDiagnostic } from "../diagnostics.js";
import KnoblyLexer from "../gen/KnoblyLexer.js";
import KnoblyParser from "../gen/KnoblyParser.js";
import { spanOf } from "./cst.js";
import { type RawDiagnostic, installRecovery, nestingOverflow } from "./recovery.js";
import { type AntlrToken, type AntlrTree, toCst, toEntryCst } from "./walk.js";
import type { Diagnostic, SourcePosition } from "../gen/api/shared.js";
import type { Node, Syntax, Token } from "../gen/api/syntax.js";
import { DiagnosticCode, describe } from "../gen/api/codes.js";
import type { TokenKind } from "../gen/api/kinds.js";

/**
 * ANTLR token type -> our TokenKind. Both come from grammar/Knobly.g4 (the generated lexer's symbolic names and
 * tools/gen-api.py's TokenKind), so a symbolic name is a TokenKind.
 */
const KIND_BY_TYPE: ReadonlyMap<number, TokenKind> = (() => {
  const map = new Map<number, TokenKind>();
  KnoblyLexer.symbolicNames.forEach((name, type) => {
    if (name !== null) map.set(type, name as TokenKind);
  });
  return map;
})();

/** The parts of antlr4's CommonTokenStream the adapter reads (its typings do not make it a TokenStream). */
interface AntlrTokenStream {
  readonly tokens: readonly AntlrToken[];
  fill(): void;
}

/** The recognizer surface the adapter uses; the lexer's and parser's inherited typings are incomplete. */
interface AntlrRecognizer {
  removeErrorListeners(): void;
}

/** The grammar's entry rules (spec 2.8, 3.3): a text a program hands to an edit or an override, parsed on its own. */
export type EntryRule = "statementsText" | "valuesText" | "valueText" | "itemsText" | "boundText" | "sliceNameText" | "nameText";

type AntlrParser = AntlrRecognizer & Record<"document" | EntryRule, () => AntlrTree>;

const EOF = -1;
const ORIGIN: SourcePosition = { offset: 0, line: 0, column: 0 };

/** The position after `text`, starting at `position` (UTF-16 units; a line ends after each "\n"). */
function advance(position: SourcePosition, text: string): SourcePosition {
  const offset = position.offset + text.length;
  const lastNewline = text.lastIndexOf("\n");
  if (lastNewline < 0) return { offset, line: position.line, column: position.column + text.length };
  const newlines = text.split("\n").length - 1;
  return { offset, line: position.line + newlines, column: text.length - lastNewline - 1 };
}

/** Our tokens, with positions computed from the token texts (ANTLR's columns count code points, not UTF-16). */
function toTokens(antlrTokens: readonly AntlrToken[]): Token[] {
  const tokens: Token[] = [];
  let at = ORIGIN;
  for (const token of antlrTokens) {
    if (token.type === EOF) continue;
    const kind = KIND_BY_TYPE.get(token.type);
    if (kind === undefined) throw new Error(`unknown ANTLR token type ${token.type}`);
    const end = advance(at, token.text);
    tokens.push({ kind, text: token.text, span: { start: at, end } });
    at = end;
  }
  return tokens;
}

/** The tokens of one text, and a parser over them with per-statement recovery reporting into `raw`. */
function prepare(text: string): { tokens: Token[]; parser: AntlrParser; raw: RawDiagnostic[] } {
  // antlr4's typings do not line up with the generated classes' parameter types: cast at the call.
  const input = CharStreams.fromString(text) as unknown as ConstructorParameters<typeof KnoblyLexer>[0];
  const lexer = new KnoblyLexer(input);
  // The lexer is total by construction (BAD_CHAR matches every character no other token can start with), so it
  // never reports an error; its default listener would print to the console.
  (lexer as unknown as AntlrRecognizer).removeErrorListeners();
  const stream = new CommonTokenStream(lexer);
  const antlrStream = stream as unknown as AntlrTokenStream;
  antlrStream.fill();
  const tokens = toTokens(antlrStream.tokens);
  const parser = new KnoblyParser(stream as unknown as ConstructorParameters<typeof KnoblyParser>[0]);
  const raw: RawDiagnostic[] = [];
  // With recovery installed the parser reports nothing to listeners; drop the default console listener anyway.
  (parser as unknown as AntlrRecognizer).removeErrorListeners();
  installRecovery(parser, (diagnostic) => raw.push(diagnostic));
  return { tokens, parser: parser as unknown as AntlrParser, raw };
}

/** The diagnostic of nesting deeper than MAX_NESTING, or undefined (run first: it would overflow the stack). */
function tooDeep(tokens: readonly Token[]): RawDiagnostic | undefined {
  const at = nestingOverflow(tokens.map((t) => t.kind));
  if (at === undefined) return undefined;
  const code = DiagnosticCode.NestingTooDeep;
  return { code, range: { start: at, end: at + 1 }, message: describe(code).message };
}

export function parse(text: string): Syntax {
  const { tokens, parser, raw } = prepare(text);
  const n = tokens.length;
  const deep = tooDeep(tokens);
  if (deep !== undefined) {
    const root: Node = { kind: "document", start: 0, end: n, children: [{ kind: "error", start: 0, end: n, children: [] }] };
    return located(tokens, root, [deep]);
  }
  return located(tokens, toCst(parser.document()), raw);
}

/**
 * Parse a text given to an edit or an override with one of the grammar's entry rules (spec 2.8): the same generated
 * parser, recovery and codes as a document, reporting the first error only, placed in the given text. The tree is a
 * `document` node over every token whose children are the text's `list` and `slice` nodes (its values are read with
 * `valuesOf`). Package-internal.
 */
export function parseEntry(text: string, rule: EntryRule): Syntax {
  const { tokens, parser, raw } = prepare(text);
  const n = tokens.length;
  const deep = tooDeep(tokens);
  if (deep !== undefined) return located(tokens, { kind: "document", start: 0, end: n, children: [] }, [deep]);
  let tree: AntlrTree;
  try {
    tree = parser[rule]();
  } catch (error) {
    // Recovery unwinds an entry rule to here after reporting its first error (recovery.ts): nothing more to read.
    if (raw.length === 0) throw error;
    return located(tokens, { kind: "document", start: 0, end: n, children: [] }, raw.slice(0, 1));
  }
  const root = toEntryCst(tree, n);
  return located(tokens, root, raw.slice(0, 1));
}

/** The syntax result, with each token-range diagnostic turned into a source span (the one place that does). */
function located(tokens: readonly Token[], root: Node, raw: readonly RawDiagnostic[]): Syntax {
  const unlocated: Syntax = { tokens, root, diagnostics: [] };
  const diagnostics: Diagnostic[] = raw.map((d) => makeDiagnostic(d.code, d.message, spanOf(unlocated, d.range)));
  return { tokens, root, diagnostics };
}
