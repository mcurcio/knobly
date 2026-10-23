/**
 * Stable diagnostic codes and the diagnostic shape every layer reports.
 *
 * This is the one registry of codes for the TypeScript package; the Python package mirrors it value for value.
 * Codes are stable across languages and releases: a code is never reused for a different meaning.
 * Ranges: 1xxx lexical, 2xxx syntax, 3xxx include graph, 4xxx typed values.
 * Every code is an error; there are no warning codes in M1.
 */

import type { ISourceSpan } from "./span.js";

export const DiagnosticCode = {
  /** A string literal reaches the end of its line or of the text without its closing quote. */
  UnterminatedString: "E1001",
  /** A character no token may start with, or a byte-order mark after the first character. */
  UnexpectedCharacter: "E1003",
  /** A token the grammar does not allow here, when no more specific code applies. */
  UnexpectedToken: "E2001",
  /** The text ends inside a block: a `{` has no matching `}`. */
  ExpectedClosingBrace: "E2003",
  /** A stray `]`, or a `[` list with no matching `]`. */
  ExpectedClosingBracket: "E2004",
  /** An `include` directive whose first value is not a string literal. */
  ExpectedStringLiteral: "E2006",
  /** A malformed slice after a word: `a[:]`, `a[1:b c]`, an unclosed slice bracket. */
  BadSlice: "E2007",
  /** A `{` that starts its line: a block must open on its directive's line. */
  BraceOnOwnLine: "E2008",
  /** Two values with no space or comment between them, such as `a"b"` (owner answer Q2 = A, vil-9ze). */
  ValuesTouch: "E2009",
  /** Blocks and lists nested deeper than 100 levels (vil-bzv.3). */
  NestingTooDeep: "E2010",
  /** The loader found no document for an include spec. */
  IncludeNotFound: "E3001",
  /** An include leads back to a document that is still being included. */
  IncludeCycle: "E3002",
  /** Includes nested deeper than the configured maximum. */
  IncludeDepthExceeded: "E3003",
  /** The loader threw or rejected for an include spec. */
  IncludeResolverFailed: "E3004",
  /** A slice or index bound that is not an integer, such as `a[x:2]` or `a[1.5]` (vil-9ze.3). */
  NonIntegerBound: "E4001",
} as const;
export type DiagnosticCode = (typeof DiagnosticCode)[keyof typeof DiagnosticCode];

/** One located problem in one source text. */
export interface IDiagnostic {
  readonly code: DiagnosticCode;
  /** Human-readable explanation. Not part of the cross-language contract; only `code` and `span` are. */
  readonly message: string;
  /** Where the problem is; a zero-width span at the end of the text for "unexpected end of input". */
  readonly span: ISourceSpan;
}

/**
 * Thrown by operations whose contract a user's input breaks (STYLE 11.6), carrying the located diagnostic.
 * `valueOf` throws it for a non-integer bound.
 */
export class DiagnosticError extends Error {
  readonly diagnostic: IDiagnostic;

  constructor(diagnostic: IDiagnostic) {
    super(diagnostic.message);
    this.name = "DiagnosticError";
    this.diagnostic = diagnostic;
  }
}
