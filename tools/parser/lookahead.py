"""The parser's decisions: LL(*) analysis of every choice point (frozen-m1.md section 3).

A choice point is an alternation, `?`, `*` or `+`. For each one the analysis builds a lookahead DFA statically from
the grammar, as ANTLR 3's LL(*) analysis does: a DFA state is a set of (alternative, parser stack) configurations, and
a state whose configurations all belong to one alternative predicts it. Past the end of the deciding rule the stack
continues at every call site of that rule (SLL: context-insensitive follow, as ANTLR 4's SLL prediction).

Refused, each with the rule and its line:
- left recursion (a rule that reaches itself without consuming a token);
- an SLL conflict: one state where two alternatives have the same stack, so no lookahead can tell them apart;
- a lookahead DFA over STATE_LIMIT states (the lookahead language is too large, or not regular);
- an alternative no lookahead ever predicts.

The result is a Plan: each parser rule as a tree of IR nodes, choice points carrying their Decision.
Python 3.9+ standard library only.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Set, Tuple

from g4 import EOF, Grammar, GrammarError, Seq

STATE_LIMIT = 400  # the largest lookahead DFA one choice point may have
DEPTH_LIMIT = 40  # the deepest chain of rule calls one lookahead step may enter without consuming a token

Frame = Tuple[tuple, ...]  # the elements still to match in one rule
Stack = Tuple[Frame, ...]  # innermost frame first
END: Stack = ((("end",),),)  # the stack of a finished parse


@dataclass
class Decision:
    rule: str
    edges: List[Dict[str, int]]  # per state: token (or EOF) to the next state; empty for an accepting state
    accept: List[int]  # per state: the predicted alternative, or -1

    @property
    def one_token(self) -> bool:
        """The first token alone decides (an LL(1) choice point)."""
        return all(self.accept[t] >= 0 for t in self.edges[0].values())


# IR: ('tok', name) | ('rule', name) | ('choice', (seq, ...), decision) | ('opt' | 'star' | 'plus', seq, decision)
Node = tuple


@dataclass
class Plan:
    grammar: Grammar
    rules: "OrderedDict[str, Tuple[Node, ...]]"  # each parser rule's body as IR
    decisions: List[Decision]  # in the order the rules are walked

    @property
    def one_token(self) -> int:
        return sum(d.one_token for d in self.decisions)

    @property
    def longer(self) -> int:
        return len(self.decisions) - self.one_token

    @property
    def longer_states(self) -> int:
        return sum(len(d.accept) for d in self.decisions if not d.one_token)


def _norm(stack: tuple) -> Stack:
    return tuple(f for f in stack if f)


def _walk(seq: Seq, cont: Stack):
    """Every element of `seq`, nested ones included, with the stack that follows it."""
    for i, e in enumerate(seq):
        after = _norm((seq[i + 1 :],) + cont)
        yield e, after
        if e[0] == "alt":
            for a in e[1]:
                yield from _walk(a, after)
        elif e[0] == "opt":
            yield from _walk(e[1], after)
        elif e[0] in ("star", "plus"):
            yield from _walk(e[1], _norm(((("star", e[1]),),) + after))


class _Analysis:
    def __init__(self, g: Grammar) -> None:
        self.g = g
        self.callsites: Dict[str, List[Stack]] = {r: [] for r in g.rules}
        for r, body in g.rules.items():
            for alt in body:
                for e, after in _walk(alt, ((("ret", r),),)):
                    if e[0] == "rule":
                        self.callsites[e[1]].append(after)
        self._left_recursion()

    # ---- left recursion

    def _nullable_rules(self) -> Set[str]:
        nullable: Set[str] = set()

        def seq_nullable(seq: Seq) -> bool:
            return all(elem_nullable(e) for e in seq)

        def elem_nullable(e: tuple) -> bool:
            k = e[0]
            if k == "tok":
                return False
            if k == "rule":
                return e[1] in nullable
            if k == "alt":
                return any(seq_nullable(a) for a in e[1])
            if k == "plus":
                return seq_nullable(e[1])
            return True  # opt, star

        changed = True
        while changed:
            changed = False
            for r, body in self.g.rules.items():
                if r not in nullable and any(seq_nullable(a) for a in body):
                    nullable.add(r)
                    changed = True
        self._seq_nullable = seq_nullable
        return nullable

    def _left_calls(self, seq: Seq, out: List[str]) -> None:
        """The rules `seq` may call before it consumes a token."""
        for e in seq:
            k = e[0]
            if k == "tok":
                return
            if k == "rule":
                out.append(e[1])
                if e[1] not in self.nullable:
                    return
            elif k == "alt":
                for a in e[1]:
                    self._left_calls(a, out)
                if not any(self._seq_nullable(a) for a in e[1]):
                    return
            else:
                self._left_calls(e[1], out)
                if k == "plus" and not self._seq_nullable(e[1]):
                    return

    def _left_recursion(self) -> None:
        self.nullable = self._nullable_rules()
        calls: Dict[str, List[str]] = {}
        for r, body in self.g.rules.items():
            out: List[str] = []
            for alt in body:
                self._left_calls(alt, out)
            calls[r] = list(OrderedDict.fromkeys(out))
        for r in self.g.rules:  # the shortest cycle back to r, if any (breadth first, in grammar order)
            paths = {c: [r, c] for c in calls[r]}
            queue = list(calls[r])
            while queue:
                q = queue.pop(0)
                if q == r:
                    raise GrammarError(f"{self.g.where(r)}: left recursion ({' -> '.join(paths[q])})")
                for c in calls[q]:
                    if c not in paths:
                        paths[c] = paths[q] + [c]
                        queue.append(c)

    # ---- one decision

    def _expand(self, stack: Stack, seen: Set[Stack], depth: int = 0) -> List[Stack]:
        """The stacks reachable from `stack` without consuming a token whose top is a token (or END)."""
        if stack in seen:
            return []
        seen.add(stack)
        if not stack:
            return [END]
        top, rest = stack[0], stack[1:]
        e, after = top[0], _norm((top[1:],) + rest)
        k = e[0]
        if k in ("tok", "end"):
            return [stack]
        if k == "ret":
            if not self.callsites[e[1]]:
                return [END]  # the end of an entry rule: the parse is complete
            return [s for cs in self.callsites[e[1]] for s in self._expand(cs, seen, depth)]
        if depth > DEPTH_LIMIT:
            raise _TooDeep()
        if k == "rule":
            return [s for alt in self.g.rules[e[1]] for s in self._expand(_norm((alt,) + after), seen, depth + 1)]
        if k == "alt":
            return [s for alt in e[1] for s in self._expand(_norm((alt,) + after), seen, depth)]
        if k == "opt":
            return self._expand(_norm((e[1],) + after), seen, depth) + self._expand(after, seen, depth)
        if k == "star":
            return self._expand(_norm((e[1], (e,)) + after), seen, depth) + self._expand(after, seen, depth)
        if k == "plus":
            return self._expand(_norm((e[1], (("star", e[1]),)) + after), seen, depth)
        raise AssertionError(k)

    def decide(self, rule: str, alt_stacks: List[Stack]) -> Decision:
        where = self.g.where(rule)
        order = {t: i for i, t in enumerate(self.g.tokens + [EOF])}
        try:
            s0 = frozenset((i, s) for i, st in enumerate(alt_stacks) for s in self._expand(st, set()))
        except _TooDeep:
            raise GrammarError(f"{where}: a choice point's lookahead enters more than {DEPTH_LIMIT} rules "
                               "without consuming a token") from None
        ids: Dict[FrozenSet[Tuple[int, Stack]], int] = {s0: 0}
        order_states: List[FrozenSet[Tuple[int, Stack]]] = [s0]
        path: List[List[str]] = [[]]
        edges: List[Dict[str, int]] = []
        accept: List[int] = []
        i = 0
        while i < len(order_states):
            here = order_states[i]
            alts = {a for a, _ in here}
            if len(alts) == 1:
                accept.append(next(iter(alts)))
                edges.append({})
                i += 1
                continue
            by_stack: Dict[Stack, Set[int]] = {}
            for a, st in here:
                by_stack.setdefault(st, set()).add(a)
            shared = sorted((sorted(als), repr(st)) for st, als in by_stack.items() if len(als) > 1)
            if shared:
                als = shared[0][0]
                seen_text = "after " + " ".join(path[i]) if path[i] else "at the first token"
                raise GrammarError(f"{where}: an SLL conflict: alternatives {als[0] + 1} and {als[1] + 1} of a choice "
                                   f"point share a continuation {seen_text}")
            accept.append(-1)
            out: Dict[str, Set[Tuple[int, Stack]]] = {}
            for a, st in here:
                if st == END:
                    continue
                tok = st[0][0][1]
                nxt = _norm((st[0][1:],) + st[1:])
                try:
                    out.setdefault(tok, set()).update((a, s) for s in self._expand(nxt, set()))
                except _TooDeep:
                    raise GrammarError(f"{where}: a choice point's lookahead enters more than {DEPTH_LIMIT} rules "
                                       "without consuming a token") from None
            e: Dict[str, int] = {}
            for tok in sorted(out, key=order.__getitem__):
                cfg = frozenset(out[tok])
                if cfg not in ids:
                    ids[cfg] = len(order_states)
                    order_states.append(cfg)
                    path.append(path[i] + [tok])
                    if len(order_states) > STATE_LIMIT:
                        raise GrammarError(f"{where}: a choice point's lookahead machine exceeds {STATE_LIMIT} states")
                e[tok] = ids[cfg]
            edges.append(e)
            i += 1
        d = Decision(rule, edges, accept)
        never = sorted(set(range(len(alt_stacks))) - set(accept))
        if never:
            raise GrammarError(f"{where}: alternative {never[0] + 1} of a choice point is never predicted")
        return d


class _TooDeep(Exception):
    pass


def analyse(g: Grammar) -> Plan:
    an = _Analysis(g)
    decisions: List[Decision] = []

    def decide(rule: str, alt_stacks: List[Stack]) -> Decision:
        d = an.decide(rule, alt_stacks)
        decisions.append(d)
        return d

    def seq(rule: str, items: Seq, after: Stack) -> Tuple[Node, ...]:
        out: List[Node] = []
        for i, e in enumerate(items):
            rest = _norm((items[i + 1 :],) + after)
            k = e[0]
            if k in ("tok", "rule"):
                out.append(e)
            elif k == "alt":
                d = decide(rule, [_norm((a,) + rest) for a in e[1]])
                out.append(("choice", tuple(seq(rule, a, rest) for a in e[1]), d))
            elif k == "opt":
                d = decide(rule, [_norm((e[1],) + rest), rest])
                out.append(("opt", seq(rule, e[1], rest), d))
            else:  # star, or plus: the decision to go round again after each pass of the body
                star = ("star", e[1])
                d = decide(rule, [_norm((e[1], (star,)) + rest), rest])
                out.append((k, seq(rule, e[1], _norm(((star,),) + rest)), d))
        return tuple(out)

    rules: "OrderedDict[str, Tuple[Node, ...]]" = OrderedDict()
    for r, body in g.rules.items():
        ret: Stack = ((("ret", r),),)
        rules[r] = seq(r, body[0], ret) if len(body) == 1 else seq(r, (("alt", body),), ret)
    return Plan(g, rules, decisions)

