/**
 * Source positions and spans, shared by tokens, values and diagnostics.
 *
 * Units (the cross-language contract, also used by the conformance corpus):
 * - `offset` and `column` count UTF-16 code units, so `text.slice(start.offset, end.offset)` is the spanned text.
 * - `line` and `column` are 0-based. A line ends after each "\n" (so "\r\n" ends one line); a lone "\r" does not.
 */

/** A point between two UTF-16 code units of the source text. */
export interface ISourcePosition {
  /** 0-based UTF-16 code-unit offset from the start of the text. */
  readonly offset: number;
  /** 0-based line number. */
  readonly line: number;
  /** 0-based UTF-16 code-unit column within the line. */
  readonly column: number;
}

/** The half-open range [start, end) of source text. `start.offset <= end.offset` always. */
export interface ISourceSpan {
  readonly start: ISourcePosition;
  readonly end: ISourcePosition;
}
