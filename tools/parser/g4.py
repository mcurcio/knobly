"""Reads grammar/Villanelle.g4 into the generator's model (design.md 1.5; frozen-m1.md section 3).

Milestone 1 skeleton: only the names (token kinds in declaration order, parser rules in declaration order) are read.
Lane P replaces this with the full reader of the .g4 subset villanelle uses (literals, character sets and their
negation, fragments, ( | ), ?, *, +, EOF) and the tree annotations (a trailing "// cst: <node kind>" comment on a
parser rule's line), refusing anything else by name and line. Python 3.9+ standard library only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


class GrammarError(Exception):
    """The grammar uses something the generator refuses (a predicate, an action, a lexer mode, left recursion, an SLL
    conflict, a lookahead machine over the state limit): the message names the rule and its line."""


@dataclass
class Grammar:
    tokens: List[str]  # lexer rule names, fragments aside, in declaration order: the token kinds (spec 3.1)
    rules: List[str]  # parser rule names in declaration order, entry rules included
    cst: Dict[str, str] = field(default_factory=dict)  # parser rule name to the node kind it opens


def _code(line: str) -> str:
    """A line with its literals emptied and its comment cut, so a ':' or ';' inside either is not read as syntax."""
    return re.sub(r"'(?:\\.|[^'\\])*'", "''", line).split("//", 1)[0]


def read(path: Path) -> Grammar:
    tokens: List[str] = []
    rules: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        code = _code(line)
        if code.lstrip().startswith("fragment"):
            continue
        for m in re.finditer(r"(?:^|;)\s*([A-Za-z][A-Za-z0-9_]*)\s*:", code):
            (tokens if m.group(1)[0].isupper() else rules).append(m.group(1))
    if not tokens or not rules:
        raise GrammarError(f"{path}: no lexer or parser rules found")
    return Grammar(tokens, rules)
