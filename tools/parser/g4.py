"""Reads grammar/Villanelle.g4 into the generator's model (design.md 1.5; frozen-m1.md section 3.1).

The .g4 subset read: a combined `grammar` header, lexer and parser rules, `fragment`, literals, character sets and
their negation (`~`), `( | )`, `?`, `*`, `+`, `EOF` and comments. Anything else (a semantic predicate, an action, a
lexer command or mode, a label, a wildcard, options) is refused by name with its line. A trailing comment
`// cst: <node kind>` on the line where a parser rule starts is that rule's tree annotation (F19).

Python 3.9+ standard library only.

The model. A rule's body is a tuple of alternatives, each a tuple of elements. Lexer elements:
    ('lit', text) | ('set', ranges) | ('ref', name) | ('alt', alternatives) | ('opt' | 'star' | 'plus', sequence)
where ranges are sorted, merged (lo, hi) code-point pairs. Parser elements, references resolved:
    ('tok', token name or 'EOF') | ('rule', name) | ('alt', alternatives) | ('opt' | 'star' | 'plus', sequence)
"""

from __future__ import annotations

import re
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tools/: the shared automaton module
from automaton import complement, normal  # noqa: E402

EOF = "EOF"  # ANTLR's end of input: the generated parser's tk::end_of_text

Element = tuple
Seq = Tuple[Element, ...]
Body = Tuple[Seq, ...]


class GrammarError(Exception):
    """The grammar uses something the generator refuses (a predicate, an action, a lexer mode, left recursion, an SLL
    conflict, a lookahead machine over the state limit, a misplaced tree annotation): the message names the rule (when
    there is one) and its line."""


@dataclass
class LexRule:
    fragment: bool
    body: Body
    line: int


@dataclass
class Grammar:
    name: str
    source: str  # the file name, for messages
    lexer: "OrderedDict[str, LexRule]"  # every lexer rule, fragments included, in declaration order
    rules: "OrderedDict[str, Body]"  # parser rules in declaration order, entry rules included, references resolved
    lines: Dict[str, int]  # every rule's line
    cst: Dict[str, str] = field(default_factory=dict)  # parser rule name to the node kind it opens (F19)

    @property
    def tokens(self) -> List[str]:
        """The token kinds: lexer rules but fragments, in declaration order (spec 3.1)."""
        return [n for n, r in self.lexer.items() if not r.fragment]

    def where(self, rule: str) -> str:
        return f"{self.source}:{self.lines[rule]}: rule {rule}"


# ------------------------------------------------------------------------------------------------ the tokenizer

_ESC = {"t": 9, "n": 10, "r": 13, "f": 12, "b": 8}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CST = re.compile(r"\bcst:\s*(\S*)")
# Keywords outside the subset, refused by name.
_REFUSED_KEYWORDS = {
    "mode": "a lexer mode",
    "options": "grammar options",
    "tokens": "a tokens block",
    "channels": "a channels block",
    "import": "a grammar import",
    "returns": "rule return values",
    "locals": "rule locals",
    "throws": "a throws clause",
    "catch": "an exception handler",
    "finally": "an exception handler",
}


@dataclass(frozen=True)
class _Tok:
    kind: str  # 'id' | 'lit' | 'set' | 'p' | 'eof'
    value: object
    line: int


def _esc(src: str, i: int) -> Tuple[int, int]:
    """Decode the escape at src[i] == '\\'; returns (code point, next index)."""
    c = src[i + 1]
    if c == "u":
        if src[i + 2] == "{":
            j = src.index("}", i + 3)
            return int(src[i + 3 : j], 16), j + 1
        return int(src[i + 2 : i + 6], 16), i + 6
    if c in _ESC:
        return _ESC[c], i + 2
    return ord(c), i + 2


def _tokenize(src: str, source: str) -> Tuple[List[_Tok], List[Tuple[int, str, int]]]:
    """-> (tokens, annotations); an annotation is (line, node kind, how many 'cst:' its comment holds)."""
    toks: List[_Tok] = []
    notes: List[Tuple[int, str, int]] = []
    i, n, line = 0, len(src), 1

    def refuse(what: str) -> GrammarError:
        return GrammarError(f"{source}:{line}: {what} is not supported")

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            found = _CST.findall(src[i:j])
            if found:
                notes.append((line, found[0], len(found)))
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0:
                raise GrammarError(f"{source}:{line}: unterminated comment")
            line += src.count("\n", i, j)
            i = j + 2
        elif c == "'":
            j, s = i + 1, []
            while j < n and src[j] not in "'\n":
                if src[j] == "\\":
                    cp, j = _esc(src, j)
                    s.append(chr(cp))
                else:
                    s.append(src[j])
                    j += 1
            if j >= n or src[j] != "'":
                raise GrammarError(f"{source}:{line}: unterminated literal")
            if not s:
                raise refuse("an empty literal")
            toks.append(_Tok("lit", "".join(s), line))
            i = j + 1
        elif c == "[":
            j, rs = i + 1, []
            while j < n and src[j] != "]":
                if src[j] == "\\":
                    lo, j = _esc(src, j)
                else:
                    lo, j = ord(src[j]), j + 1
                hi = lo
                if src[j] == "-" and src[j + 1] != "]":
                    if src[j + 1] == "\\":
                        hi, j = _esc(src, j + 1)
                    else:
                        hi, j = ord(src[j + 1]), j + 2
                if hi < lo:
                    raise GrammarError(f"{source}:{line}: the character range {lo:#x}-{hi:#x} is reversed")
                rs.append((lo, hi))
            if j >= n:
                raise GrammarError(f"{source}:{line}: unterminated character set")
            toks.append(_Tok("set", normal(rs), line))
            i = j + 1
        elif c.isalpha() or c == "_":
            m = _IDENT.match(src, i)
            assert m
            word = m.group()
            if word in _REFUSED_KEYWORDS:
                raise refuse(_REFUSED_KEYWORDS[word])
            toks.append(_Tok("id", word, line))
            i = m.end()
        elif c == "{":
            j = src.find("}", i)
            raise refuse("a semantic predicate" if j >= 0 and src.startswith("?", j + 1) else "an action")
        elif src.startswith("->", i):
            raise refuse("a lexer command")
        elif c == "@":
            raise refuse("a named action")
        elif c == ".":
            raise refuse("the wildcard '.'")
        elif c == "=" or src.startswith("+=", i):
            raise refuse("an element label")
        elif c == "#":
            raise refuse("an alternative label")
        elif c == "<":
            raise refuse("an element option")
        elif c in ":;|()*+?~":
            toks.append(_Tok("p", c, line))
            i += 1
        else:
            raise refuse(f"the character {c!r}")
    toks.append(_Tok("eof", None, line))
    return toks, notes


# --------------------------------------------------------------------------------------------------- the reader


def parse(src: str, source: str = "grammar") -> Grammar:
    toks, notes = _tokenize(src, source)
    pos = 0

    def peek() -> _Tok:
        return toks[pos]

    def is_p(t: _Tok, c: str) -> bool:
        return t.kind == "p" and t.value == c

    def take(kind: str, value: Optional[str] = None) -> _Tok:
        nonlocal pos
        t = toks[pos]
        if t.kind != kind or (value is not None and t.value != value):
            got = "the end of the file" if t.kind == "eof" else repr(t.value)
            raise GrammarError(f"{source}:{t.line}: expected {value or kind}, found {got}")
        pos += 1
        return t

    def alts() -> Body:
        out = [seq()]
        while is_p(peek(), "|"):
            take("p", "|")
            out.append(seq())
        return tuple(out)

    def seq() -> Seq:
        out: List[Element] = []
        while peek().kind in ("id", "lit", "set") or is_p(peek(), "(") or is_p(peek(), "~"):
            e = atom()
            t = peek()
            if t.kind == "p" and t.value in ("?", "*", "+"):
                take("p")
                body = e[1][0] if e[0] == "alt" and len(e[1]) == 1 else (e,)
                e = ({"?": "opt", "*": "star", "+": "plus"}[t.value], body)
                if is_p(peek(), "?"):
                    raise GrammarError(f"{source}:{peek().line}: a non-greedy operator is not supported")
            out.append(e)
        return tuple(out)

    def atom() -> Element:
        t = peek()
        if is_p(t, "("):
            take("p")
            b = alts()
            take("p", ")")
            return ("alt", b)
        if is_p(t, "~"):
            take("p")
            u = peek()
            if u.kind == "set":
                take("set")
                return ("set", complement(u.value))
            if u.kind == "lit" and len(str(u.value)) == 1:
                take("lit")
                return ("set", complement(((ord(str(u.value)), ord(str(u.value))),)))
            raise GrammarError(f"{source}:{u.line}: '~' takes a character set or a one-character literal")
        take(t.kind)
        return ("ref", t.value) if t.kind == "id" else (t.kind, t.value)

    t = take("id")
    if t.value in ("lexer", "parser"):
        raise GrammarError(f"{source}:{t.line}: a {t.value} grammar is not supported (one combined grammar)")
    if t.value != "grammar":
        raise GrammarError(f"{source}:{t.line}: expected 'grammar', found {t.value!r}")
    name = str(take("id").value)
    take("p", ";")

    lexer: "OrderedDict[str, LexRule]" = OrderedDict()
    raw: "OrderedDict[str, Body]" = OrderedDict()
    lines: Dict[str, int] = {}
    while peek().kind != "eof":
        frag = False
        if peek().kind == "id" and peek().value == "fragment":
            take("id")
            frag = True
        head = take("id")
        rule = str(head.value)
        if rule in lines:
            raise GrammarError(f"{source}:{head.line}: rule {rule} is defined twice (first on line {lines[rule]})")
        if rule == EOF:
            raise GrammarError(f"{source}:{head.line}: EOF is ANTLR's end of input and cannot be redefined")
        lines[rule] = head.line
        take("p", ":")
        body = tuple(_flatten(a) for a in alts())
        take("p", ";")
        if rule[0].isupper():
            lexer[rule] = LexRule(frag, body, head.line)
        elif frag:
            raise GrammarError(f"{source}:{head.line}: rule {rule}: 'fragment' applies to lexer rules only")
        else:
            raw[rule] = body
    if not lexer or not raw:
        raise GrammarError(f"{source}: no lexer or parser rules found")

    g = Grammar(name, source, lexer, OrderedDict(), lines)
    lit_token = {
        r.body[0][0][1]: n
        for n, r in lexer.items()
        if not r.fragment and len(r.body) == 1 and len(r.body[0]) == 1 and r.body[0][0][0] == "lit"
    }
    g.rules = OrderedDict((r, tuple(_resolve(g, r, raw, lit_token, a) for a in body)) for r, body in raw.items())
    g.cst = _annotations(g, notes)
    return g


def read(path: Path) -> Grammar:
    return parse(path.read_text(encoding="utf-8"), path.name)


def _flatten(seq: Seq) -> Seq:
    """Unwrap one-alternative groups into the surrounding sequence."""
    out: List[Element] = []
    for e in seq:
        if e[0] == "alt" and len(e[1]) == 1:
            out.extend(_flatten(e[1][0]))
        elif e[0] == "alt":
            out.append(("alt", tuple(_flatten(a) for a in e[1])))
        elif e[0] in ("opt", "star", "plus"):
            out.append((e[0], _flatten(e[1])))
        else:
            out.append(e)
    return tuple(out)


def _resolve(g: Grammar, rule: str, raw: "OrderedDict[str, Body]", lit_token: Dict[str, str], seq: Seq) -> Seq:
    out: List[Element] = []
    for e in seq:
        k = e[0]
        if k == "lit":
            if e[1] not in lit_token:
                raise GrammarError(f"{g.where(rule)}: the literal {e[1]!r} has no token rule of its own")
            out.append(("tok", lit_token[e[1]]))
        elif k == "ref":
            ref = e[1]
            if ref == EOF:
                out.append(("tok", EOF))
            elif ref[0].isupper():
                if ref not in g.lexer:
                    raise GrammarError(f"{g.where(rule)}: unknown token {ref}")
                if g.lexer[ref].fragment:
                    raise GrammarError(f"{g.where(rule)}: the fragment {ref} is not a token")
                out.append(("tok", ref))
            else:
                if ref not in raw:
                    raise GrammarError(f"{g.where(rule)}: unknown rule {ref}")
                out.append(("rule", ref))
        elif k == "alt":
            out.append(("alt", tuple(_resolve(g, rule, raw, lit_token, a) for a in e[1])))
        elif k in ("opt", "star", "plus"):
            out.append((k, _resolve(g, rule, raw, lit_token, e[1])))
        else:
            raise GrammarError(f"{g.where(rule)}: a character set in a parser rule is not supported")
    return tuple(out)


def _annotations(g: Grammar, notes: List[Tuple[int, str, int]]) -> Dict[str, str]:
    """Each `// cst: <kind>` must end the line where a parser rule starts, one per rule."""
    starts = {line: r for r, line in g.lines.items() if r in g.rules}
    out: Dict[str, str] = OrderedDict()
    for line, kind, count in notes:
        rule = starts.get(line)
        if rule is None:
            raise GrammarError(f"{g.source}:{line}: the tree annotation 'cst: {kind}' names no rule "
                               "(it must end the line where a parser rule starts)")
        if count > 1 or rule in out:
            raise GrammarError(f"{g.where(rule)}: two tree annotations on one rule")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", kind):
            raise GrammarError(f"{g.where(rule)}: the tree annotation names no node kind ({kind!r})")
        out[rule] = kind
    return out


def ebnf_annotations(src: str) -> Dict[str, str]:
    """The `/* cst: kind */` annotations of grammar/villanelle.ebnf, rule names lowered at the first letter."""
    out: Dict[str, str] = OrderedDict()
    for m in re.finditer(r"^(\w+)\s*::=.*?/\*\s*cst:\s*(\w+)\s*\*/", src, re.M):
        out[m.group(1)[0].lower() + m.group(1)[1:]] = m.group(2)
    return out
