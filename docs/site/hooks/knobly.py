"""Fail the build unless ```knobly blocks are highlighted by the grammar's own lexer, and every one lexes cleanly.

pymdownx.highlight shows a block as plain text when its language has no lexer, so without this check a missing
knobly-pygments install (lexer/) would pass the build unhighlighted. A block holding a token the grammar calls an
error (an unterminated string, a bad escape, a lone '$', a character outside the alphabet) fails it too. Run by
`hooks:` in mkdocs.yml.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mkdocs.exceptions import PluginError
from pygments.lexers import get_lexer_by_name
from pygments.token import Error
from pygments.util import ClassNotFound

REPO = Path(__file__).resolve().parents[3]
BLOCK = re.compile(r"^```knobly[^\n]*\n(.*?)^```", re.M | re.S)
# A block whose whole body is one pymdownx.snippets include (base_path is the repository root): the file is checked.
INCLUDE = re.compile(r'\A--8<--\s+"([^"]+)"\s*\Z')


def on_config(config: Any) -> Any:
    try:
        get_lexer_by_name("knobly")
    except ClassNotFound as e:
        raise PluginError("no Pygments lexer for knobly: install docs/site/lexer (uv sync)") from e
    return config


def on_page_markdown(markdown: str, page: Any, config: Any, files: Any) -> str:
    lexer = get_lexer_by_name("knobly")
    for block in BLOCK.finditer(markdown):
        text = block.group(1)
        include = INCLUDE.match(text.strip())
        if include:
            text = (REPO / include.group(1)).read_text(encoding="utf-8")
        bad = [v for t, v in lexer.get_tokens(text) if t in Error]
        if bad:
            raise PluginError(f"{page.file.src_path}: a knobly block has text the grammar cannot lex: {bad!r}")
    return markdown
