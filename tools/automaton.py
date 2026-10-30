"""Code-point automata, the one home of the machinery both C++ generators use: the lexer of knobly's own parser
generator (tools/parser/lexer.py, tools/parser/g4.py) and the pattern matchers of the C++ API emitter
(tools/api/emit_cpp.py). Code-point range sets, a Thompson NFA over them, the subset construction and Moore's
minimisation. Python 3.9+ standard library only.

A range set is a sorted tuple of disjoint, non-adjacent (lo, hi) code-point intervals. A DFA is a list of rows, one
per state (state 0 the start), each row its (lo, hi, target) moves sorted by lo and disjoint, beside a list of each
state's accept label (-1 for none; a lower label wins where several meet, ANTLR's first-rule tie).
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Sequence, Tuple

MAX_CP = 0x10FFFF

Ranges = Tuple[Tuple[int, int], ...]
Move = Tuple[int, int, int]  # (lo, hi, target state)


def normal(ranges: Iterable[Tuple[int, int]]) -> Ranges:
    """The ranges sorted, with overlapping and adjacent ones joined."""
    out: List[Tuple[int, int]] = []
    for lo, hi in sorted(ranges):
        if out and lo <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return tuple(out)


def complement(ranges: Iterable[Tuple[int, int]]) -> Ranges:
    """Every code point the ranges leave out."""
    out, at = [], 0
    for lo, hi in normal(ranges):
        if lo > at:
            out.append((at, lo - 1))
        at = hi + 1
    if at <= MAX_CP:
        out.append((at, MAX_CP))
    return tuple(out)


class Nfa:
    """A Thompson NFA: per state, its empty moves and its (ranges, target) moves; some states carry an accept label."""

    def __init__(self) -> None:
        self.eps: List[List[int]] = []
        self.edges: List[List[Tuple[Ranges, int]]] = []
        self.accept: Dict[int, int] = {}

    def state(self) -> int:
        self.eps.append([])
        self.edges.append([])
        return len(self.eps) - 1

    def ranges(self, ranges: Ranges) -> Tuple[int, int]:
        """A fragment matching one code point of the ranges: its (start, end) states."""
        a, z = self.state(), self.state()
        self.edges[a].append((ranges, z))
        return a, z

    def chain(self, fragments: Sequence[Tuple[int, int]]) -> Tuple[int, int]:
        """The fragments one after another (none: the empty text)."""
        a = z = self.state()
        for s, t in fragments:
            self.eps[z].append(s)
            z = t
        return a, z

    def choice(self, fragments: Sequence[Tuple[int, int]]) -> Tuple[int, int]:
        """Any one of the fragments."""
        a, z = self.state(), self.state()
        for s, t in fragments:
            self.eps[a].append(s)
            self.eps[t].append(z)
        return a, z

    def repeat(self, fragment: Tuple[int, int], optional: bool, many: bool) -> Tuple[int, int]:
        """The fragment once, or also never (optional), or also again and again (many)."""
        s, t = fragment
        a, z = self.state(), self.state()
        self.eps[a].append(s)
        self.eps[t].append(z)
        if optional:
            self.eps[a].append(z)
        if many:
            self.eps[t].append(s)
        return a, z


def determinize(nfa: Nfa, start: int) -> Tuple[List[List[Move]], List[int]]:
    """The subset construction: the DFA's moves and each state's accept label, the lowest label among the NFA states
    it holds (-1 for none). States are numbered in breadth-first order from the start."""

    def close(states: Iterable[int]) -> FrozenSet[int]:
        stack = list(states)
        seen = set(stack)
        while stack:
            for t in nfa.eps[stack.pop()]:
                if t not in seen:
                    seen.add(t)
                    stack.append(t)
        return frozenset(seen)

    first = close([start])
    ids = {first: 0}
    order = [first]
    trans: List[List[Move]] = []
    accept: List[int] = []
    i = 0
    while i < len(order):
        here = order[i]
        labels = [nfa.accept[s] for s in here if s in nfa.accept]
        accept.append(min(labels) if labels else -1)
        edges = [(rs, t) for s in sorted(here) for rs, t in nfa.edges[s]]
        cuts = sorted({lo for rs, _ in edges for lo, _ in rs} | {hi + 1 for rs, _ in edges for _, hi in rs})
        out: List[Move] = []
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
    return trans, accept


def minimize(trans: List[List[Move]], accept: List[int]) -> Tuple[List[List[Move]], List[int]]:
    """The DFA with equivalent states merged (Moore's partition refinement; states with different accept labels never
    merge), renumbered breadth-first from the start, so the result does not depend on how the input was numbered."""
    block = [accept[s] for s in range(len(trans))]
    while True:
        signature = [(block[s], tuple(_renamed(trans[s], block))) for s in range(len(trans))]
        ids: Dict[tuple, int] = {}
        for s in range(len(trans)):
            ids.setdefault(signature[s], len(ids))
        refined = [ids[signature[s]] for s in range(len(trans))]
        if len(set(refined)) == len(set(block)):
            break
        block = refined
    rows: Dict[int, List[Move]] = {}
    labels: Dict[int, int] = {}
    for s in range(len(trans)):
        rows[refined[s]] = _renamed(trans[s], refined)
        labels[refined[s]] = accept[s]
    number = {refined[0]: 0}
    queue = [refined[0]]
    while queue:
        for _, _, t in rows[queue.pop(0)]:
            if t not in number:
                number[t] = len(number)
                queue.append(t)
    out: List[List[Move]] = [[] for _ in number]
    out_accept = [-1] * len(number)
    for b, n in number.items():
        out[n] = _renamed(rows[b], [number.get(i, -1) for i in range(max(rows) + 1)])
        out_accept[n] = labels[b]
    return out, out_accept


def _renamed(row: List[Move], name: List[int]) -> List[Move]:
    """A state's moves with each target renamed, adjacent ranges to one target joined."""
    out: List[Move] = []
    for lo, hi, t in row:
        if out and out[-1][2] == name[t] and out[-1][1] + 1 == lo:
            out[-1] = (out[-1][0], hi, name[t])
        else:
            out.append((lo, hi, name[t]))
    return out
