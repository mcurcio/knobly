"""``format_diagnostic`` (spec 2.7, spec/contract.md 2): a located diagnostic as text for people. Low level, because it
reads the source line from a document graph (spec/schema/api.json puts it in the written layer, as TypeScript's
``ts/src/written/format.ts``). It builds on the people forms (``str()`` of a located diagnostic and of a step)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from villanelle._report import LocatedDiagnostic
    from villanelle.written._model import DocumentGraph


def format_diagnostic(diagnostic: LocatedDiagnostic, graph: DocumentGraph | None = None) -> str:
    lines = [str(diagnostic)]
    document = None if graph is None else graph.documents.get(diagnostic.place.resolved_path)
    if document is not None:
        start, end = diagnostic.place.span.start, diagnostic.place.span.end
        # A line ends at "\n" only ("\r\n" loses its "\r"); never splitlines(), which also breaks at a lone "\r".
        source_lines = document.text.split("\n")
        if start.line < len(source_lines):
            line = source_lines[start.line]
            # Only a "\r" that a "\n" follows is part of the line end; a lone "\r" ending the text stays.
            if start.line < len(source_lines) - 1:
                line = line.removesuffix("\r")
            width = end.column - start.column if end.line == start.line else len(line) - start.column
            # Tabs stay tabs so the caret lines up under the same characters; every other character becomes a space.
            pad = "".join("\t" if char == "\t" else " " for char in line[: start.column])
            lines.append(line)
            lines.append(pad + "^" * max(1, width))
    lines.extend(f"  via {step}" for step in diagnostic.via)
    return "\n".join(lines)
