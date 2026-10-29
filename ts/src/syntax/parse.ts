/**
 * The adapter: the only module that touches the ANTLR runtime and the generated parser (src/gen/, made by
 * tools/gen.sh). Everything it returns is ours: IToken, INode, IDiagnostic.
 */

import { CharStreams, CommonTokenStream } from "antlr4";

import { DiagnosticCode, type IDiagnostic, makeDiagnostic, messageOf } from "../diagnostics.js";
import VillanelleLexer from "../gen/VillanelleLexer.js";
import VillanelleParser from "../gen/VillanelleParser.js";
import type { ISourcePosition } from "../span.js";
import { type INode, type ISyntax, spanOf } from "./cst.js";
import { type IRawDiagnostic, installRecovery, nestingOverflow } from "./recovery.js";
import type { IToken, TokenKind } from "./tokens.js";
import { type IAntlrToken, type IAntlrTree, toCst, toEntryCst } from "./walk.js";

/**
 * ANTLR token type -> our TokenKind. Both come from grammar/Villanelle.g4 (the generated lexer's symbolic names and
 * tools/gen-api.py's TokenKind), so a symbolic name is a TokenKind.
 */
const KIND_BY_TYPE: ReadonlyMap<number, TokenKind> = (() => {
  const map = new Map<number, TokenKind>();
  VillanelleLexer.symbolicNames.forEach((name, type) => {
    if (name !== null) map.set(type, name as TokenKind);
  });
  return map;
})();

/** The parts of antlr4's CommonTokenStream the adapter reads (its typings do not make it a TokenStream). */
interface IAntlrTokenStream {
  readonly tokens: readonly IAntlrToken[];
  fill(): void;
}

/** The recognizer surface the adapter uses; the lexer's and parser's inherited typings are incomplete. */
interface IAntlrRecognizer {
  removeErrorListeners(): void;
}

/** The grammar's entry rules (spec 2.8, 3.3): a text a program hands to an edit or an override, parsed on its own. */
export type EntryRule = "statementsText" | "valuesText" | "valueText" | "itemsText" | "boundText" | "sliceNameText" | "nameText";

type IAntlrParser = IAntlrRecognizer & Record<"document" | EntryRule, () => IAntlrTree>;

const EOF = -1;
const ORIGIN: ISourcePosition = { offset: 0, line: 0, column: 0 };

/** The position after `text`, starting at `position` (UTF-16 units; a line ends after each "\n"). */
function advance(position: ISourcePosition, text: string): ISourcePosition {
  const offset = position.offset + text.length;
  const lastNewline = text.lastIndexOf("\n");
  if (lastNewline < 0) return { offset, line: position.line, column: position.column + text.length };
  const newlines = text.split("\n").length - 1;
  return { offset, line: position.line + newlines, column: text.length - lastNewline - 1 };
}

/** Our tokens, with positions computed from the token texts (ANTLR's columns count code points, not UTF-16). */
function toTokens(antlrTokens: readonly IAntlrToken[]): IToken[] {
  const tokens: IToken[] = [];
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
function prepare(text: string): { tokens: IToken[]; parser: IAntlrParser; raw: IRawDiagnostic[] } {
  // antlr4's typings do not line up with the generated classes' parameter types: cast at the call.
  const input = CharStreams.fromString(text) as unknown as ConstructorParameters<typeof VillanelleLexer>[0];
  const lexer = new VillanelleLexer(input);
  // The lexer is total by construction (BAD_CHAR matches every character no other token can start with), so it
  // never reports an error; its default listener would print to the console.
  (lexer as unknown as IAntlrRecognizer).removeErrorListeners();
  const stream = new CommonTokenStream(lexer);
  const antlrStream = stream as unknown as IAntlrTokenStream;
  antlrStream.fill();
  const tokens = toTokens(antlrStream.tokens);
  const parser = new VillanelleParser(stream as unknown as ConstructorParameters<typeof VillanelleParser>[0]);
  const raw: IRawDiagnostic[] = [];
  // With recovery installed the parser reports nothing to listeners; drop the default console listener anyway.
  (parser as unknown as IAntlrRecognizer).removeErrorListeners();
  installRecovery(parser, (diagnostic) => raw.push(diagnostic));
  return { tokens, parser: parser as unknown as IAntlrParser, raw };
}

/** The diagnostic of nesting deeper than MAX_NESTING, or undefined (run first: it would overflow the stack). */
function tooDeep(tokens: readonly IToken[]): IRawDiagnostic | undefined {
  const at = nestingOverflow(tokens.map((t) => t.kind));
  if (at === undefined) return undefined;
  const code = DiagnosticCode.NestingTooDeep;
  return { code, range: { start: at, end: at + 1 }, message: messageOf(code) };
}

/**
 * Parse one text. Synchronous, pure and total: it never throws for any input string, and never reads files.
 * Errors are reported in `diagnostics`; the tree still covers every token.
 */
export function parse(text: string): ISyntax {
  const { tokens, parser, raw } = prepare(text);
  const n = tokens.length;
  const deep = tooDeep(tokens);
  if (deep !== undefined) {
    const root: INode = { kind: "document", start: 0, end: n, children: [{ kind: "error", start: 0, end: n, children: [] }] };
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
export function parseEntry(text: string, rule: EntryRule): ISyntax {
  const { tokens, parser, raw } = prepare(text);
  const n = tokens.length;
  const deep = tooDeep(tokens);
  if (deep !== undefined) return located(tokens, { kind: "document", start: 0, end: n, children: [] }, [deep]);
  let tree: IAntlrTree;
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
function located(tokens: readonly IToken[], root: INode, raw: readonly IRawDiagnostic[]): ISyntax {
  const unlocated: ISyntax = { tokens, root, diagnostics: [] };
  const diagnostics: IDiagnostic[] = raw.map((d) => makeDiagnostic(d.code, d.message, spanOf(unlocated, d.range)));
  return { tokens, root, diagnostics };
}
