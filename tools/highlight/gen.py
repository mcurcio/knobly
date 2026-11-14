"""The highlighters, generated from the grammar's token rules and the highlight model (grammar/highlight.json).

    python3 tools/highlight/gen.py ts <out.ts>          the TypeScript highlighter's tables (tools/gen.sh ts)
    python3 tools/highlight/gen.py textmate <out.json>  the TextMate grammar, knobly.tmLanguage.json (a release asset)
    python3 tools/highlight/gen.py check                the model against the grammar (tools/check.sh)

Design: design/releases-and-highlighting.md section 2. Every highlighter scans with the minimized longest-match DFA
that knobly's own parser generator builds from Knobly.g4 (tools/parser/lexer.py), so each token it reports is the
token the parsers see, and adds one rule: the head rule (a statement's first WORD is its name).

The TextMate grammar is exact, not a copy of the token rules. TextMate takes the first pattern that matches, where
the lexer takes the longest match. Every state of the minimized DFA but the start accepts, so the longest match is
"run until no move applies": for each state the generator writes a regex for the texts that reach it (by state
elimination) followed by a negative lookahead of the characters that leave it, and exactly one state's pattern
matches at any position. `load` refuses a grammar without that property, and one whose start state does not take
every code point (a text that does not lex would need a fallback).

Python 3.9+ standard library only. Nothing it writes is committed (owner, 2026-10-23).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "parser"))
import g4  # noqa: E402  (g4 puts tools/ on the path)
import lexer as g4lexer  # noqa: E402
from automaton import MAX_CP, Move, minimize, normal  # noqa: E402

GRAMMAR = REPO / "grammar" / "Knobly.g4"
MODEL = REPO / "grammar" / "highlight.json"
SCOPE = "source.knobly"


class ModelError(Exception):
    pass


@dataclass
class Model:
    tokens: List[str]  # token kinds in grammar order; accept values index this list
    trans: List[List[Move]]  # the minimized DFA, state 0 the start
    accept: List[int]
    classes: Dict[str, dict]  # class name -> {"doc", "textmate", "pygments"}, in the model's order
    token_class: Dict[str, str]  # token kind -> class
    token_scope: Dict[str, Optional[str]]  # token kind -> TextMate scope (the class's unless the kind names its own)
    token_pygments: Dict[str, str]  # token kind -> Pygments token type (the class's unless the kind names its own)
    starts: List[str]
    filler: List[str]
    head_class: Dict[str, str]  # token kind -> class it takes as a statement's first token


def load(grammar: Path = GRAMMAR, model: Path = MODEL) -> Model:
    """The model, checked against the grammar; raises ModelError naming the first problem."""
    dfa = g4lexer.build(g4.read(grammar))
    trans, accept = minimize(dfa.trans, dfa.accept)
    raw = json.loads(model.read_text(encoding="utf-8"))
    where = model.relative_to(REPO) if model.is_relative_to(REPO) else model
    classes: Dict[str, dict] = raw["classes"]
    entries: Dict[str, dict] = raw["tokens"]
    head = raw["head"]

    missing = [t for t in dfa.tokens if t not in entries]
    if missing:
        raise ModelError(f"{where}: no class for the token kinds {', '.join(missing)} (add them to \"tokens\")")
    extra = [t for t in entries if t not in dfa.tokens]
    if extra:
        raise ModelError(f"{where}: \"tokens\" names {', '.join(extra)}, which the grammar does not declare")
    for name, entry in entries.items():
        if entry["class"] not in classes:
            raise ModelError(f"{where}: token {name}: unknown class {entry['class']!r}")
    for name in [*head["starts"], *head["filler"], *head["classes"]]:
        if name not in dfa.tokens:
            raise ModelError(f"{where}: \"head\" names {name}, which the grammar does not declare")
    for name, cls in head["classes"].items():
        if cls not in classes:
            raise ModelError(f"{where}: head class of {name}: unknown class {cls!r}")
        if name in head["starts"] or name in head["filler"]:
            raise ModelError(f"{where}: {name} cannot be both a statement's first token and a start or filler")

    # The two DFA properties the generated highlighters rely on.
    if accept[0] >= 0:
        raise ModelError(f"{grammar.name}: the start state accepts (a token matches the empty text)")
    lazy = [s for s in range(1, len(trans)) if accept[s] < 0]
    if lazy:
        raise ModelError(f"{grammar.name}: DFA states {lazy} do not accept, so the longest match is not 'run until no "
                         "move applies' and the TextMate grammar cannot be exact (tools/highlight/gen.py)")
    if normal((lo, hi) for lo, hi, _ in trans[0]) != ((0, MAX_CP),):
        raise ModelError(f"{grammar.name}: some code point starts no token (BAD_CHAR should take every other one)")
    # A start token must be one character that no other token starts with, so a TextMate statement can end before it.
    for name in head["starts"]:
        kind = dfa.tokens.index(name)
        firsts = [(lo, hi, t) for lo, hi, t in trans[0] if accept[t] == kind]
        if len(firsts) != 1 or firsts[0][0] != firsts[0][1] or trans[firsts[0][2]]:
            raise ModelError(f"{where}: head start {name} must be one character no other token starts with")

    return Model(
        tokens=list(dfa.tokens),
        trans=trans,
        accept=accept,
        classes=classes,
        token_class={t: entries[t]["class"] for t in dfa.tokens},
        token_scope={t: entries[t].get("textmate", classes[entries[t]["class"]]["textmate"]) for t in dfa.tokens},
        token_pygments={t: entries[t].get("pygments", classes[entries[t]["class"]]["pygments"]) for t in dfa.tokens},
        starts=list(head["starts"]),
        filler=list(head["filler"]),
        head_class=dict(head["classes"]),
    )


def start_chars(m: Model) -> List[int]:
    """The code point of each head start token (one character each: `load` checks it)."""
    return [next(lo for lo, _, t in m.trans[0] if m.tokens[m.accept[t]] == name) for name in m.starts]


# --------------------------------------------------------------------------------------------- TypeScript tables


def emit_ts(m: Model) -> str:
    """The TypeScript highlighter's tables: the DFA as flat (lo, hi, target) triples per state, and the classes."""

    def arr(values: Sequence[Union[int, str]]) -> str:
        return "[" + ", ".join(json.dumps(v) for v in values) + "]"

    rows = ",\n  ".join(arr([x for move in row for x in move]) for row in m.trans)
    lines = [
        "// Generated by tools/highlight/gen.py from grammar/Knobly.g4 and grammar/highlight.json. Do not edit.",
        'import type { TokenKind } from "./api/kinds.js";',
        "",
        "/** The highlight classes, in the model's order. */",
        f"export const CLASSES = {arr(list(m.classes))} as const;",
        "",
        "/** Token kinds in grammar order: `ACCEPT` indexes this list. */",
        f"export const KINDS: readonly TokenKind[] = {arr(m.tokens)};",
        "",
        "/** Per token kind (same index as `KINDS`), its class index; as a statement's first token, `HEAD`'s. */",
        f"export const CLASS: readonly number[] = {arr([list(m.classes).index(m.token_class[t]) for t in m.tokens])};",
        f"export const HEAD: readonly number[] = "
        f"{arr([list(m.classes).index(m.head_class[t]) if t in m.head_class else -1 for t in m.tokens])};",
        "",
        "/** Per token kind: 1 if it starts a statement (the next token is a statement's first), 2 if it is filler. */",
        f"export const ROLE: readonly number[] = "
        f"{arr([1 if t in m.starts else 2 if t in m.filler else 0 for t in m.tokens])};",
        "",
        "/** The minimized longest-match DFA: per state, its moves as flat (lo, hi, target) code-point triples. */",
        f"export const MOVES: readonly (readonly number[])[] = [\n  {rows},\n];",
        "",
        "/** Per state, the index into `KINDS` of the token it accepts (-1 for the start state only). */",
        f"export const ACCEPT: readonly number[] = {arr(m.accept)};",
        "",
    ]
    return "\n".join(lines)


# -------------------------------------------------------------------------------------------- regexes from the DFA

# A regex term: ("set", ranges) one code point; ("cat", terms); ("alt", terms); ("star", term); EPS the empty text.
Term = tuple
EPS: Term = ("cat", ())


def _cat(*parts: Term) -> Term:
    out: List[Term] = []
    for p in parts:
        out.extend(p[1] if p[0] == "cat" else (p,))
    return out[0] if len(out) == 1 else ("cat", tuple(out))


def _alt(*parts: Term) -> Term:
    sets: List[Tuple[int, int]] = []
    rest: List[Term] = []
    for p in parts:
        for q in p[1] if p[0] == "alt" else (p,):
            if q[0] == "set":
                sets.extend(q[1])
            elif q not in rest:
                rest.append(q)
    out = ([("set", normal(sets))] if sets else []) + rest
    return out[0] if len(out) == 1 else ("alt", tuple(out))


def _star(p: Term) -> Term:
    return EPS if p == EPS else p if p[0] == "star" else ("star", p)


def reach(m: Model, target: int) -> Term:
    """A regex for the texts that take the DFA from its start to `target`: state elimination over a generalized NFA
    with a new start and final state, eliminating the cheapest state (fewest in times out edges) first."""
    start, final = -1, -2
    edges: Dict[Tuple[int, int], Term] = {}

    def add(a: int, b: int, t: Term) -> None:
        edges[(a, b)] = _alt(edges[(a, b)], t) if (a, b) in edges else t

    for s, row in enumerate(m.trans):
        for lo, hi, t in row:
            add(s, t, ("set", ((lo, hi),)))
    add(start, 0, EPS)
    add(target, final, EPS)
    left = set(range(len(m.trans)))
    while left:
        def cost(s: int) -> int:
            ins = sum(1 for (a, b) in edges if b == s and a != s)
            outs = sum(1 for (a, b) in edges if a == s and b != s)
            return ins * outs

        s = min(sorted(left), key=cost)
        loop = _star(edges.pop((s, s))) if (s, s) in edges else EPS
        ins = [(a, t) for (a, b), t in edges.items() if b == s]
        outs = [(b, t) for (a, b), t in edges.items() if a == s]
        for a, _ in ins:
            del edges[(a, s)]
        for b, _ in outs:
            del edges[(s, b)]
        for a, ta in ins:
            for b, tb in outs:
                add(a, b, _cat(ta, loop, tb))
        left.discard(s)
    return edges.get((start, final), ("alt", ()))


def _cp(c: int) -> str:
    ch = chr(c)
    return ch if ch.isascii() and ch.isalnum() else f"\\x{{{c:X}}}"


def _class(ranges: Sequence[Tuple[int, int]]) -> str:
    if len(ranges) == 1 and ranges[0][0] == ranges[0][1]:
        return _cp(ranges[0][0])
    body = "".join(_cp(lo) if lo == hi else f"{_cp(lo)}-{_cp(hi)}" for lo, hi in ranges)
    return f"[{body}]"


def render(t: Term, ctx: str = "top") -> str:
    """Oniguruma syntax; every group is non-capturing (the begin pattern numbers its own groups)."""
    kind = t[0]
    if kind == "set":
        return _class(t[1])
    if kind == "cat":
        return "".join(render(p, "cat") for p in t[1])
    if kind == "star":
        inner = render(t[1], "star")
        atomic = t[1][0] == "set"
        return f"{inner}*" if atomic else f"(?:{inner})*"
    # alt: an alternative that is the empty text becomes '?'
    parts = [p for p in t[1] if p != EPS]
    opt = len(parts) < len(t[1])
    body = "|".join(render(p, "alt") for p in parts)
    if opt:
        return f"{body}?" if len(parts) == 1 and parts[0][0] == "set" else f"(?:{body})?"
    return body if ctx in ("top",) else f"(?:{body})"


def token_patterns(m: Model) -> Dict[str, str]:
    """Per token kind, the regex that matches exactly that kind's longest match at a position: one alternative per
    DFA state accepting it, each followed by a negative lookahead of the characters that leave that state."""
    out: Dict[str, List[str]] = {t: [] for t in m.tokens}
    for s in range(1, len(m.trans)):
        body = render(reach(m, s))
        leave = normal((lo, hi) for lo, hi, _ in m.trans[s])
        out[m.tokens[m.accept[s]]].append(f"(?:{body})" + (f"(?!{_class(leave)})" if leave else ""))
    return {t: "|".join(alts) for t, alts in out.items() if alts}


# ----------------------------------------------------------------------------------------------------- TextMate


def emit_textmate(m: Model) -> dict:
    """The TextMate grammar. Its states are the head rule's: `#statements` (the next token is a statement's first)
    and inside a statement, which begins at its first token and ends before the next start token."""
    pats = token_patterns(m)
    starts = set(m.starts)
    end = "(?=" + _class(normal((c, c) for c in start_chars(m))) + ")"

    def match(kind: str, scope: Optional[str] = None) -> dict:
        name = scope if scope is not None else m.token_scope[kind]
        return {"match": pats[kind], **({"name": name} if name else {})}

    def statement(kinds: List[str], head: bool) -> dict:
        groups: Dict[str, dict] = {}
        alts = []
        for i, kind in enumerate(kinds, 1):
            alts.append(f"({pats[kind]})")
            scope = m.classes[m.head_class[kind]]["textmate"] if head else m.token_scope[kind]
            if scope:
                groups[str(i)] = {"name": scope}
        return {"begin": "|".join(alts), "beginCaptures": groups, "end": end, "patterns": [{"include": "#values"}]}

    firsts = [t for t in m.tokens if t not in starts and t not in m.filler and t in pats]
    heads = [t for t in firsts if t in m.head_class]
    others = [t for t in firsts if t not in m.head_class]
    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "knobly",
        "scopeName": SCOPE,
        "fileTypes": ["knobly"],
        "comment": "Generated by tools/highlight/gen.py from grammar/Knobly.g4 and grammar/highlight.json "
                   "(https://github.com/mcurcio/knobly). Do not edit.",
        "patterns": [{"include": "#statements"}],
        "repository": {
            "statements": {
                "patterns": [*(match(t) for t in m.filler), *(match(t) for t in m.starts),
                             *([statement(heads, True)] if heads else []), statement(others, False)],
            },
            "values": {"patterns": [match(t) for t in m.tokens if t not in starts and t in pats]},
        },
    }


def scope_classes(m: Model) -> Dict[str, str]:
    """Every TextMate scope the grammar names, to its class (the check's reading of a tokenized line)."""
    out = {c["textmate"]: name for name, c in m.classes.items() if c["textmate"]}
    for kind, scope in m.token_scope.items():
        if scope:
            out[scope] = m.token_class[kind]
    return out


def main(argv: List[str]) -> int:
    if not argv or argv[0] not in ("ts", "textmate", "check") or (argv[0] != "check" and len(argv) != 2):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        m = load()
    except ModelError as e:
        print(f"highlight: {e}", file=sys.stderr)
        return 1
    if argv[0] == "check":
        sizes = {t: len(p) for t, p in token_patterns(m).items()}
        print(f"highlight: {len(m.tokens)} token kinds, {len(m.classes)} classes, {len(m.trans)} DFA states; "
              f"TextMate patterns {sum(sizes.values())} characters (longest {max(sizes, key=sizes.get)}, "
              f"{max(sizes.values())})")
        return 0
    out = Path(argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    if argv[0] == "ts":
        text = emit_ts(m)
    else:
        text = json.dumps(emit_textmate(m), indent=2, ensure_ascii=False) + "\n"
    out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
