/**
 * `format diagnostic` (spec 2.3): a located diagnostic as text for people. Low level, because it reads the source
 * line from a document graph.
 */

import type { IPlace } from "../origin.js";
import type { ILocatedDiagnostic } from "../report.js";
import type { IDocumentGraph } from "./model.js";

/** `path:line:col`, 1-based, for people. */
function where(place: IPlace): string {
  return `${place.resolvedPath}:${String(place.span.start.line + 1)}:${String(place.span.start.column + 1)}`;
}

/**
 * `path:line:col: code: message` (1-based line and column, for people), then the source line and a caret under the
 * span when `graph` holds the file (its current text), then one `  via <kind> <name> at path:line:col` line per
 * step (rasl-ynq). Reads text only from `graph`; never does I/O.
 */
export function formatDiagnostic(diagnostic: ILocatedDiagnostic, graph?: IDocumentGraph): string {
  const { place, via } = diagnostic;
  const lines = [`${where(place)}: ${diagnostic.code}: ${diagnostic.message}`];
  const source = graph?.documents.get(place.resolvedPath)?.text;
  if (source !== undefined) {
    const { start, end } = place.span;
    const lineStart = start.offset - start.column;
    const lineEnd = source.slice(lineStart).search(/\r\n|\n|\r/u);
    const text = lineEnd < 0 ? source.slice(lineStart) : source.slice(lineStart, lineStart + lineEnd);
    const width = end.line === start.line ? end.column - start.column : text.length - start.column;
    // Tabs stay tabs so the caret lines up under the same characters.
    const pad = text.slice(0, start.column).replace(/[^\t]/g, " ");
    lines.push(text, `${pad}${"^".repeat(Math.max(1, width))}`);
  }
  for (const step of via) lines.push(`  via ${step.kind} ${step.name} at ${where(step.place)}`);
  return lines.join("\n");
}
