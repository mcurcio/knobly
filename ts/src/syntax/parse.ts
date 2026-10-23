/**
 * The adapter: the only module that touches the ANTLR runtime and the generated parser (src/gen/, made by
 * tools/gen.sh). Everything it returns is ours: IToken, INode, IDiagnostic.
 */

import { CharStreams, CommonTokenStream } from "antlr4";

import { DiagnosticCode, type IDiagnostic } from "../diagnostics.js";
import VillanelleLexer from "../gen/VillanelleLexer.js";
import VillanelleParser from "../gen/VillanelleParser.js";
import type { ISourcePosition, ISourceSpan } from "../span.js";
import type { ISyntax } from "./cst.js";
import { type IToken, TokenKind } from "./tokens.js";
import { type IAntlrToken, type IAntlrTree, toCst } from "./walk.js";

/** ANTLR token type -> our TokenKind, from the generated lexer's names; throws at load on a name we do not know. */
const KIND_BY_TYPE: ReadonlyMap<number, TokenKind> = (() => {
  const known = new Set<string>(Object.values(TokenKind));
  const map = new Map<number, TokenKind>();
  VillanelleLexer.symbolicNames.forEach((name, type) => {
    if (name === null) return;
    if (!known.has(name)) throw new Error(`grammar token ${name} is not a TokenKind`);
    map.set(type, name as TokenKind);
  });
  return map;
})();

/** The parts of antlr4's CommonTokenStream the adapter reads (its typings do not make it a TokenStream). */
interface IAntlrTokenStream {
  readonly tokens: readonly IAntlrToken[];
  fill(): void;
}

/**
 * An ANTLR error listener. antlr4's typings do not export ErrorListener, and the runtime calls all four methods
 * (the three report* ones during full-context prediction), so a listener implements every one.
 */
interface IAntlrErrorListener {
  syntaxError(recognizer: unknown, offending: IAntlrToken | null, line: number, column: number, message: string): void;
  reportAmbiguity(): void;
  reportAttemptingFullContext(): void;
  reportContextSensitivity(): void;
}

/** The recognizer surface the adapter uses; the lexer's and parser's inherited typings are incomplete. */
interface IAntlrRecognizer {
  removeErrorListeners(): void;
  addErrorListener(listener: IAntlrErrorListener): void;
}

interface IAntlrParser extends IAntlrRecognizer {
  document(): IAntlrTree;
}

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

function codeFor(token: IToken | undefined, index: number): DiagnosticCode {
  if (token?.kind === TokenKind.BadChar || (token?.kind === TokenKind.Bom && index > 0)) {
    return DiagnosticCode.UnexpectedCharacter;
  }
  if (token?.kind === TokenKind.UnterminatedString) return DiagnosticCode.UnterminatedString;
  return DiagnosticCode.UnexpectedToken;
}

/** Reports each syntax error as our diagnostic, located by the offending token. */
class DiagnosticListener implements IAntlrErrorListener {
  readonly diagnostics: IDiagnostic[] = [];

  constructor(
    private readonly tokens: readonly IToken[],
    private readonly endOfText: ISourceSpan,
  ) {}

  syntaxError(_recognizer: unknown, offending: IAntlrToken | null, _line: number, _column: number, message: string): void {
    const index = offending?.tokenIndex ?? -1;
    const token = offending === null || offending.type === EOF ? undefined : this.tokens[index];
    this.diagnostics.push({ code: codeFor(token, index), message, span: token?.span ?? this.endOfText });
  }

  /** Ambiguity reports are diagnostics for grammar authors, not errors; tools/check.sh proves there are none. */
  reportAmbiguity(): void {}
  reportAttemptingFullContext(): void {}
  reportContextSensitivity(): void {}
}

/**
 * Parse one text. Synchronous, pure and total: it never throws for any input string, and never reads files.
 * Errors are reported in `diagnostics`; the tree still covers every token.
 */
export function parse(text: string): ISyntax {
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
  const end = tokens.at(-1)?.span.end ?? ORIGIN;

  const parser = new VillanelleParser(stream as unknown as ConstructorParameters<typeof VillanelleParser>[0]) as unknown as IAntlrParser;
  const listener = new DiagnosticListener(tokens, { start: end, end });
  parser.removeErrorListeners();
  parser.addErrorListener(listener);
  const root = toCst(parser.document());
  return { tokens, root, diagnostics: listener.diagnostics };
}
