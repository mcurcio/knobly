"""The lexer: every token rule to one longest-match DFA over code points (frozen-m1.md section 3).

Each token rule becomes a Thompson NFA over code-point ranges; subset construction makes the DFA (both from
tools/automaton.py, which the C++ API emitter's pattern matchers share). A DFA state accepts
the token rule written first among the rules it accepts (ANTLR's tie rule); the generated scanner keeps the last
accepting state it passed, so the match is the longest. Python 3.9+ standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from g4 import Body, Grammar, GrammarError
from automaton import Nfa, determinize  # g4 put tools/ on the path

Range = Tuple[int, int, int]  # (lo, hi, target state)


@dataclass
class Dfa:
    tokens: List[str]  # token kinds in grammar order; accept values index this list
    trans: List[List[Range]]  # per state, its outgoing ranges sorted by lo, disjoint
    accept: List[int]  # per state, the token accepted there, or -1

    def match(self, text: str, at: int = 0) -> Tuple[int, int]:
        """The longest match at `at` as (token index or -1, end): the generated scanner's algorithm, for the tests."""
        state, best, i = 0, (-1, at), at
        while i < len(text):
            cp = ord(text[i])
            nxt = next((t for lo, hi, t in self.trans[state] if lo <= cp <= hi), -1)
            if nxt < 0:
                break
            state, i = nxt, i + 1
            if self.accept[state] >= 0:
                best = (self.accept[state], i)
        return best


def build(g: Grammar) -> Dfa:
    nfa = Nfa()
    start = nfa.state()
    tokens = g.tokens

    def body(b: Body, active: Tuple[str, ...]) -> Tuple[int, int]:
        return nfa.choice([nfa.chain([elem(e, active) for e in alt]) for alt in b])

    def elem(e: tuple, active: Tuple[str, ...]) -> Tuple[int, int]:
        k = e[0]
        if k == "lit":
            return nfa.chain([nfa.ranges(((ord(ch), ord(ch)),)) for ch in e[1]])
        if k == "set":
            return nfa.ranges(e[1])
        if k == "ref":
            name = e[1]
            if name not in g.lexer:
                raise GrammarError(f"{g.where(active[0])}: unknown lexer rule {name}")
            if name in active:
                raise GrammarError(f"{g.where(active[0])}: the lexer rule {name} is recursive")
            return body(g.lexer[name].body, active + (name,))
        if k == "alt":
            return body(e[1], active)
        return nfa.repeat(body((e[1],), active), k in ("opt", "star"), k in ("star", "plus"))

    for prio, name in enumerate(tokens):
        s, t = body(g.lexer[name].body, (name,))
        nfa.eps[start].append(s)
        nfa.accept[t] = prio
    trans, accept = determinize(nfa, start)
    if accept[0] >= 0:
        raise GrammarError(f"{g.where(tokens[accept[0]])}: the token matches the empty text")
    return Dfa(tokens, trans, accept)
