"""The lexer: every token rule to one longest-match DFA over code points (frozen-m1.md section 3).

Each token rule becomes a Thompson NFA over code-point ranges; subset construction makes the DFA. A DFA state accepts
the token rule written first among the rules it accepts (ANTLR's tie rule); the generated scanner keeps the last
accepting state it passed, so the match is the longest. Python 3.9+ standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Tuple

from g4 import Body, Grammar, GrammarError

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


class _Nfa:
    def __init__(self) -> None:
        self.eps: List[List[int]] = []
        self.edges: List[List[Tuple[Tuple[Tuple[int, int], ...], int]]] = []
        self.accept: Dict[int, int] = {}

    def state(self) -> int:
        self.eps.append([])
        self.edges.append([])
        return len(self.eps) - 1


def build(g: Grammar) -> Dfa:
    nfa = _Nfa()
    start = nfa.state()
    tokens = g.tokens

    def body(b: Body, active: Tuple[str, ...]) -> Tuple[int, int]:
        a, z = nfa.state(), nfa.state()
        for alt in b:
            cur = a
            for e in alt:
                s, t = elem(e, active)
                nfa.eps[cur].append(s)
                cur = t
            nfa.eps[cur].append(z)
        return a, z

    def elem(e: tuple, active: Tuple[str, ...]) -> Tuple[int, int]:
        k = e[0]
        if k == "lit":
            a = cur = nfa.state()
            for ch in e[1]:
                nxt = nfa.state()
                nfa.edges[cur].append((((ord(ch), ord(ch)),), nxt))
                cur = nxt
            return a, cur
        if k == "set":
            a, z = nfa.state(), nfa.state()
            nfa.edges[a].append((e[1], z))
            return a, z
        if k == "ref":
            name = e[1]
            if name not in g.lexer:
                raise GrammarError(f"{g.where(active[0])}: unknown lexer rule {name}")
            if name in active:
                raise GrammarError(f"{g.where(active[0])}: the lexer rule {name} is recursive")
            return body(g.lexer[name].body, active + (name,))
        if k == "alt":
            return body(e[1], active)
        s, t = body((e[1],), active)
        a, z = nfa.state(), nfa.state()
        nfa.eps[a].append(s)
        nfa.eps[t].append(z)
        if k in ("opt", "star"):
            nfa.eps[a].append(z)
        if k in ("star", "plus"):
            nfa.eps[t].append(s)
        return a, z

    for prio, name in enumerate(tokens):
        s, t = body(g.lexer[name].body, (name,))
        nfa.eps[start].append(s)
        nfa.accept[t] = prio
    return _determinize(nfa, start, tokens, g)


def _determinize(nfa: _Nfa, start: int, tokens: List[str], g: Grammar) -> Dfa:
    def close(states: Iterable[int]) -> FrozenSet[int]:
        stack = list(states)
        seen = set(stack)
        while stack:
            for t in nfa.eps[stack.pop()]:
                if t not in seen:
                    seen.add(t)
                    stack.append(t)
        return frozenset(seen)

    s0 = close([start])
    ids = {s0: 0}
    order = [s0]
    trans: List[List[Range]] = []
    accept: List[int] = []
    i = 0
    while i < len(order):
        here = order[i]
        acc = [nfa.accept[s] for s in here if s in nfa.accept]
        accept.append(min(acc) if acc else -1)
        edges = [(rs, t) for s in sorted(here) for rs, t in nfa.edges[s]]
        cuts = sorted({lo for rs, _ in edges for lo, _ in rs} | {hi + 1 for rs, _ in edges for _, hi in rs})
        out: List[Range] = []
        for a, b in zip(cuts, cuts[1:]):
            targets = [t for rs, t in edges if any(lo <= a <= hi for lo, hi in rs)]
            if not targets:
                continue
            nxt = close(targets)
            if nxt not in ids:
                ids[nxt] = len(order)
                order.append(nxt)
            j = ids[nxt]
            if out and out[-1][2] == j and out[-1][1] == a - 1:
                out[-1] = (out[-1][0], b - 1, j)
            else:
                out.append((a, b - 1, j))
        trans.append(out)
        i += 1
    if accept[0] >= 0:
        raise GrammarError(f"{g.where(tokens[accept[0]])}: the token matches the empty text")
    return Dfa(tokens, trans, accept)
