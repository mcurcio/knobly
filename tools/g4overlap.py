"""Token checks for the lexer rules of a .g4 (the subset Villanelle.g4 uses): each non-fragment
lexer rule becomes a regex over code points, and interegular decides two things.
  1. Overlap: for every pair of token kinds, whether some string matches both.
  2. Adjacency (longest match): for every pair of tokens A B the parser rules can place next to each other with
     nothing between them (from their FIRST and LAST sets), whether the lexer can swallow the start of B into a
     longer token (some x in A and a non-empty prefix z of some y in B with x+z one token): then A B can never be
     written, as '1~3' would lex as one word if '~' were a word character. A run that starts with a token of the
     `gap` or `filler` rules (spaces, comments, line breaks) is exempt: two spaces are one SPACE, and a comment
     swallowing the rest of its line is the comment rule, not a lost construct. So is a run that ends in a COMMENT:
     after a word's first character '#' is a word character (spec 3.1), so a comment needs a gap before it, and
     the gap rule letting a comment follow a value directly is never reached.
Refuses lexer commands, modes, actions, predicates and non-greedy loops."""
import re, sys, itertools, interegular
src = open(sys.argv[1], encoding='utf-8').read()
def die(m): sys.exit('g4overlap: refused: ' + m)
TOK = re.compile(r"""\s+|//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\])*'|~?\[(?:\\.|[^\]\\])*\]|[A-Za-z_][A-Za-z0-9_]*|->|\*\?|\+\?|\?\?|[:;|()?*+~.{}]""", re.S)
toks, pos = [], 0
while pos < len(src):
    m = TOK.match(src, pos)
    if not m: die('text %r' % src[pos:pos + 20])
    pos = m.end(); t = m.group()
    if not (t.isspace() or t.startswith('//') or t.startswith('/*')): toks.append(t)
def esc(s, i):
    """ANTLR escape at s[i] == '\\' -> (code point, next index)."""
    c = s[i + 1]
    if c == 'u':
        if s[i + 2] == '{': j = s.index('}', i); return int(s[i + 3:j], 16), j + 1
        return int(s[i + 2:i + 6], 16), i + 6
    return {'t': 9, 'n': 10, 'r': 13, 'f': 12, 'b': 8}.get(c, ord(c)), i + 2
def ranges(body):
    rng, i = [], 0
    while i < len(body):
        a, i = esc(body, i) if body[i] == '\\' else (ord(body[i]), i + 1)
        if i + 1 < len(body) and body[i] == '-':
            b, i = esc(body, i + 1) if body[i + 1] == '\\' else (ord(body[i + 1]), i + 2); rng.append((a, b))
        else: rng.append((a, a))
    return rng
CUTS = {0, 0x110000}
def classes():
    """Alphabet compression: code points split into intervals no set boundary crosses; each
    interval is one symbol (a representative character), so the FSMs stay small."""
    cuts = sorted(CUTS); return list(zip(cuts, cuts[1:]))
def rep(k): return re.escape(chr(0x4E00 + k))
def cls(body, neg):
    rng, out = ranges(body), []
    for k, (lo, hi) in enumerate(classes()):
        inside = any(a <= lo and hi - 1 <= b for a, b in rng)
        if inside != neg: out.append(rep(k))
    return '[' + ''.join(out) + ']'
def lit_char(c):
    k = next(k for k, (lo, hi) in enumerate(classes()) if lo <= c < hi); return rep(k)
rules, frags, prules, i = {}, {}, {}, 3
while i < len(toks):
    frag = toks[i] == 'fragment'; i += frag
    name = toks[i]; j = toks.index(';', i); body = toks[i + 2:j]; i = j + 1
    if not name[0].isupper(): prules[name] = body; continue
    for t in body:
        if t in ('->', '{', '}', '*?', '+?', '??', 'mode'): die('%r in %s' % (t, name))
    (frags if frag else rules)[name] = body
def rx(body):
    out = []
    for t in body:
        if t.startswith("'"):
            s, k, lit = t[1:-1], 0, ''
            while k < len(s):
                c, k = esc(s, k) if s[k] == '\\' else (ord(s[k]), k + 1); lit += lit_char(c)
            out.append('(?:' + lit + ')')
        elif t.startswith('~['): out.append(cls(t[2:-1], True))
        elif t.startswith('['): out.append(cls(t[1:-1], False))
        elif t in frags: out.append('(?:' + rx(frags[t]) + ')')
        elif t == '.': die('wildcard')
        elif t == '~': die('~ before a non-set')
        elif t[0].isupper(): die('token reference %s inside a lexer rule' % t)
        else: out.append(t)                                  # ( ) | ? * +
    return ''.join(out)
for body in list(rules.values()) + list(frags.values()):
    for t in body:
        if t.startswith('~[') or t.startswith('['):
            for a, b in ranges(t[t.index('[') + 1:-1]): CUTS.update((a, b + 1))
        elif t.startswith("'"):
            q, k = t[1:-1], 0
            while k < len(q):
                c, k = esc(q, k) if q[k] == '\\' else (ord(q[k]), k + 1); CUTS.update((c, c + 1))
print('alphabet: %d symbol classes' % len(classes()))
fsm = {n: interegular.parse_pattern(rx(b)).to_fsm() for n, b in rules.items()}
bad = 0
for a, b in itertools.combinations(rules, 2):
    common = fsm[a] & fsm[b]
    if not common.empty():
        bad += 1; ex = next(iter(common.strings()))
        w = ''.join(chr(classes()[ord(str(x)) - 0x4E00][0]) for x in ex)
        print('OVERLAP %s / %s, e.g. %r' % (a, b, w))
print('%d token kinds, %d pairs, %d overlapping' % (len(rules), len(rules) * (len(rules) - 1) // 2, bad))

# --- 2. adjacency ------------------------------------------------------------------------------------------------
lits = {b[0]: n for n, b in rules.items() if len(b) == 1 and b[0].startswith("'")}
def tree(body):
    """A parser rule body as nested ('alt'|'seq', [..]), ('opt'|'star'|'plus', x), ('t', token), ('n', rule)."""
    pos = [0]
    def alt():
        out = [seq()]
        while pos[0] < len(body) and body[pos[0]] == '|': pos[0] += 1; out.append(seq())
        return ('alt', out)
    def seq():
        out = []
        while pos[0] < len(body) and body[pos[0]] not in ('|', ')'):
            t = body[pos[0]]; pos[0] += 1
            if t == '(': x = alt(); pos[0] += 1
            elif t.startswith("'"):
                if t not in lits: die('literal %s is no token' % t)
                x = ('t', lits[t])
            elif t == 'EOF': x = ('seq', [])
            elif t[0].isupper(): x = ('t', t)
            elif t in prules: x = ('n', t)
            else: die('unknown %r in a parser rule' % t)
            if pos[0] < len(body) and body[pos[0]] in ('?', '*', '+'):
                x = ({'?': 'opt', '*': 'star', '+': 'plus'}[body[pos[0]]], x); pos[0] += 1
            out.append(x)
        return ('seq', out)
    return alt()
trees = {n: tree(b) for n, b in prules.items()}
N, F, L = {n: False for n in trees}, {n: set() for n in trees}, {n: set() for n in trees}
def info(x, pairs):
    """(nullable, FIRST, LAST) of x; adds the adjacent token pairs inside x to pairs."""
    k = x[0]
    if k == 't': return False, {x[1]}, {x[1]}
    if k == 'n': return N[x[1]], set(F[x[1]]), set(L[x[1]])
    if k == 'alt':
        parts = [info(y, pairs) for y in x[1]]
        return any(p[0] for p in parts), set().union(*(p[1] for p in parts)), set().union(*(p[2] for p in parts))
    if k == 'seq':
        nul, first, last = True, set(), set()
        for y in x[1]:
            n, f, l = info(y, pairs)
            pairs.update((a, b) for a in last for b in f)
            if nul: first |= f
            last = last | l if n else set(l)
            nul = nul and n
        return nul, first, last
    n, f, l = info(x[1], pairs)
    if k in ('star', 'plus'): pairs.update((a, b) for a in l for b in f)
    return n or k != 'plus', f, l
changed = True
while changed:
    changed = False
    for n, t in trees.items():
        got = info(t, set())
        if (got[0], got[1], got[2]) != (N[n], F[n], L[n]): N[n], F[n], L[n] = got; changed = True
pairs = set()
for t in trees.values(): info(t, pairs)
trivia = set()
for n in ('gap', 'filler'):
    if n in trees: info(trees[n], set()); trivia |= F[n] | L[n]
empty = interegular.parse_pattern('').to_fsm()
def prefixes(m):
    """The non-empty prefixes of m's strings."""
    live = {q for q in m.states if m.islive(q)}
    return interegular.fsm.FSM(m.alphabet, m.states, m.initial, live, m.map).difference(empty)
lost = 0
for a, b in sorted(pairs):
    if a not in fsm or b not in fsm or a in trivia or b == 'COMMENT': continue
    joined = fsm[a] + prefixes(fsm[b])
    for t in rules:
        common = joined & fsm[t]
        if not common.empty():
            lost += 1; ex = next(iter(common.strings()))
            w = ''.join(chr(classes()[ord(str(x)) - 0x4E00][0]) for x in ex)
            print('ADJACENT %s %s lexes as one %s, e.g. %r' % (a, b, t, w))
print('%d adjacent token pairs, %d lost to longest match' % (len(pairs), lost))
sys.exit(1 if bad or lost else 0)
