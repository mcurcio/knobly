"""``format_diagnostic`` (spec 2.3): a located diagnostic as text for people. Low level, because it reads the source
line from a document graph (spec/schema/api.json puts it in the written layer, as TypeScript's
``ts/src/written/format.ts``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from villanelle.origin import Place
from villanelle.report import LocatedDiagnostic

if TYPE_CHECKING:
    from villanelle.written.model import DocumentGraph


def format_diagnostic(diagnostic: LocatedDiagnostic, graph: DocumentGraph | None = None) -> str:
    """``path:line:col: code: message`` (1-based line and column, for people), then the source line and a caret under
    the span when ``graph`` holds the file (its current text), then one ``  via <kind> <name> at path:line:col`` line
    per step. Reads text only from ``graph``; never does I/O."""
    lines = [f"{_place(diagnostic.place)}: {diagnostic.code}: {diagnostic.message}"]
    document = None if graph is None else graph.documents.get(diagnostic.place.resolved_path)
    if document is not None:
        start, end = diagnostic.place.span.start, diagnostic.place.span.end
        source_lines = document.text.split("\n")
        if start.line < len(source_lines):
            line = source_lines[start.line].removesuffix("\r")
            # Columns count UTF-16 code units, as TypeScript's strings do: a character above U+FFFF counts two.
            units = [2 if ord(c) > 0xFFFF else 1 for c in line]
            width = end.column - start.column if end.line == start.line else sum(units) - start.column
            # Tabs stay tabs so the caret lines up under the same characters; every other unit becomes a space.
            pad: list[str] = []
            column = 0
            for char, size in zip(line, units, strict=True):
                if column >= start.column:
                    break
                pad.append("\t" if char == "\t" else " " * size)
                column += size
            lines.append(line)
            lines.append("".join(pad) + "^" * max(1, width))
    lines.extend(f"  via {step.kind} {step.name} at {_place(step.place)}" for step in diagnostic.via)
    return "\n".join(lines)


def _place(place: Place) -> str:
    """``path:line:col``, 1-based, for people."""
    position = place.span.start
    return f"{place.resolved_path}:{position.line + 1}:{position.column + 1}"
