/**
 * `format diagnostic` (spec 2.3): a located diagnostic as text for people. Low level, because it reads the source
 * line from a document graph.
 */

import { locatedForm, stepForm } from "../people.js";
import type { ILocatedDiagnostic } from "../report.js";
import type { IDocumentGraph } from "./model.js";

/**
 * The located diagnostic's people form, `path:line:col: code: message` (spec/contract.md 2), then the source line and
 * a caret under the span when `graph` holds the file (its current text), then one `  via <step>` line per step,
 * innermost first. A line ends only at `"\n"` (`"\r\n"` included); a lone `"\r"` stays in the line. Columns and
 * carets count UTF-16 code units. Reads text only from `graph`; never does I/O.
 */
export function formatDiagnostic(diagnostic: ILocatedDiagnostic, graph?: IDocumentGraph): string {
  const { place, via } = diagnostic;
  const lines = [locatedForm(diagnostic)];
  const source = graph?.documents.get(place.resolvedPath)?.text;
  if (source !== undefined) {
    const { start, end } = place.span;
    const lineStart = start.offset - start.column;
    const lineEnd = source.slice(lineStart).search(/\r?\n/u);
    const text = lineEnd < 0 ? source.slice(lineStart) : source.slice(lineStart, lineStart + lineEnd);
    const width = end.line === start.line ? end.column - start.column : text.length - start.column;
    // Tabs stay tabs so the caret lines up under the same characters.
    const pad = text.slice(0, start.column).replace(/[^\t]/g, " ");
    lines.push(text, `${pad}${"^".repeat(Math.max(1, width))}`);
  }
  for (const step of via) lines.push(`  via ${stepForm(step)}`);
  return lines.join("\n");
}
