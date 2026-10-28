/**
 * Stable diagnostic codes and the diagnostic shape every layer reports.
 *
 * This is the one registry of codes for the TypeScript package; the Python package mirrors it value for value.
 * Codes are stable across languages and releases: a code is never reused for a different meaning.
 * Ranges: 1xxx lexical, 2xxx syntax, 3xxx files and extensions, 4xxx values, 5xxx expansion (variables, snippets,
 * limits), 6xxx reserved for the deferred sugar (none yet). A program's own codes are namespaced ("rasl/no-graph"),
 * so they can never collide with these (ProgramCode, load/report.ts).
 * Every code is an error; there are no warning codes.
 */

import type { ISourceSpan } from "./span.js";

export const DiagnosticCode = {
  /** A string literal reaches the end of its line or of the text without its closing quote. */
  UnterminatedString: "E1001",
  /** A character no token may start with, or a byte-order mark after the first character. */
  UnexpectedCharacter: "E1003",
  /** A `$` not followed by a variable name (letters, digits, `_`). */
  LoneDollar: "E1004",
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
  /** An `include` whose values are not exactly one quoted path. Replaces E2006 once the include extension lands. */
  IncludeBadPath: "E3005",
  /** An extension threw something other than a DiagnosticError while giving its specs. */
  ExtensionFailed: "E3006",
  /** A slice or index bound that is not an integer, such as `a[x:2]` or `a[1.5]` (vil-9ze.3). */
  NonIntegerBound: "E4001",
  /** A reader asked for a kind of value the argument is not (`integer()` on a list). */
  WrongValueKind: "E4002",
  /** A backslash escape other than the six of EscapeText (owner, v6 values: "The EBNF's rules win"). */
  BadEscape: "E4003",
  /** A word that is not a NumberText (JSON number), read as a number. */
  NotANumber: "E4004",
  /** A word that is not an IntegerText, read as an integer. */
  NotAnInteger: "E4005",
  /** A word other than `true` or `false`, read as a boolean. */
  NotABoolean: "E4006",
  /** A `$name` with no `set` visible at that place and no value handed in by the program. */
  UnknownVariable: "E5001",
  /** Two `set` lines for one name in one block. */
  VariableSetTwice: "E5002",
  /** A `use` naming no snippet visible at that place. */
  UnknownSnippet: "E5003",
  /** A `use` with a different number of values than its snippet has parameters. */
  SnippetArity: "E5004",
  /** Two `snippet` lines for one name in one block. */
  SnippetDefinedTwice: "E5005",
  /** A `use` or an extension directive that reaches itself again (a snippet using itself, a file including itself). */
  ExpansionCycle: "E5006",
  /** `use` and extension directives nested deeper than 16 places. Replaces E3003 once the include extension lands. */
  ExpansionTooDeep: "E5007",
  /** More than 100,000 directives after expansion. */
  TooManyDirectives: "E5008",
  /** A `set` that is not `set $name value...;`. */
  BadSet: "E5009",
  /** A `snippet` that is not `snippet name $param... { ... }`, or names a parameter twice. */
  BadSnippet: "E5010",
  /** A `use` that is not `use name value...;`. */
  BadUse: "E5011",
  /** An extension directive whose block holds a line other than `set`. */
  ExtensionBlockNotSet: "E5012",
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
