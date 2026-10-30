"""The parser generator's own tests (frozen-m1.md section 3.1). Python standard library unittest; run by
`python3 tools/parser/gen.py --check`, or alone: `python3 tools/parser/test_parser.py`."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import List

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cpp  # noqa: E402
import g4  # noqa: E402
import gen  # noqa: E402
import lexer  # noqa: E402
import lookahead  # noqa: E402


def grammar(src: str) -> g4.Grammar:
    return g4.parse("grammar T;\n" + src, "t.g4")


def refusal(src: str) -> str:
    with unittest.TestCase().assertRaises(g4.GrammarError) as caught:
        gen.build(grammar(src))
    return str(caught.exception)


def predict(d: lookahead.Decision, tokens: List[str]) -> int:
    """Run a decision's lookahead DFA over `tokens` (then end of input) as the generated predict_<n> does."""
    s = 0
    for tok in tokens + [g4.EOF] * 8:
        if d.accept[s] >= 0:
            return d.accept[s]
        if tok not in d.edges[s]:
            return -1
        s = d.edges[s][tok]
    return d.accept[s]


class Lexer(unittest.TestCase):
    def test_longest_match_and_first_rule_tie(self) -> None:
        dfa = lexer.build(grammar("s : (IF | ID)* EOF ;\nIF : 'if' ;\nID : [a-z]+ ;\n"))
        self.assertEqual(dfa.match("if"), (0, 2))  # IF and ID both match two letters: IF is written first
        self.assertEqual(dfa.match("iffy"), (1, 4))  # ID matches longer
        self.assertEqual(dfa.match("i"), (1, 1))
        self.assertEqual(dfa.match("!"), (-1, 0))

    def test_knobly_tokens(self) -> None:
        g = g4.read(gen.GRAMMAR)
        dfa = lexer.build(g)
        kind = {text: g.tokens[dfa.match(text)[0]] for text in ("-12", "-12a", "$", "$x", "@set", "a:b", "'raw\\'")}
        self.assertEqual(kind, {"-12": "INTEGER", "-12a": "DIGIT_WORD", "$": "LONE_DOLLAR", "$x": "VARIABLE",
                                "@set": "AT_WORD", "a:b": "WORD", "'raw\\'": "STRING"})
        self.assertEqual(dfa.match('"bad\\q"')[0], g.tokens.index("BAD_ESCAPE"))
        self.assertEqual(dfa.match("a b"), (g.tokens.index("WORD"), 1))

    def test_empty_token_refused(self) -> None:
        self.assertIn("matches the empty text", refusal("s : A EOF ;\nA : 'a'* ;\n"))


class Decisions(unittest.TestCase):
    def test_one_token_decision(self) -> None:
        plan = lookahead.analyse(grammar("s : (A B | C) EOF ;\nA : 'a' ;\nB : 'b' ;\nC : 'c' ;\n"))
        (d,) = plan.decisions
        self.assertTrue(d.one_token)
        self.assertEqual((predict(d, ["A", "B"]), predict(d, ["C"]), predict(d, ["B"])), (0, 1, -1))

    def test_longer_decision(self) -> None:
        plan = lookahead.analyse(grammar("s : (A* B | A* C) EOF ;\nA : 'a' ;\nB : 'b' ;\nC : 'c' ;\n"))
        d = plan.decisions[0]
        self.assertFalse(d.one_token)
        self.assertEqual(predict(d, ["A", "A", "A", "B"]), 0)
        self.assertEqual(predict(d, ["A", "C"]), 1)
        self.assertEqual(predict(d, ["A", "A"]), -1)  # dies at the end of the text: the error is reported there

    def test_knobly_value_needs_two_tokens(self) -> None:
        plan = lookahead.analyse(g4.read(gen.GRAMMAR))
        (d,) = [d for d in plan.decisions if d.rule == "value"]
        self.assertFalse(d.one_token)
        self.assertEqual(predict(d, ["WORD", "LBRACK", "INTEGER"]), 6)  # slicedWord
        self.assertEqual(predict(d, ["WORD", "SEMI"]), 0)  # a plain WORD
        self.assertEqual(predict(d, ["LBRACK"]), 7)  # list

    def test_knobly_numbers(self) -> None:
        g = g4.read(gen.GRAMMAR)
        plan, dfa = gen.build(g)
        # the probe's numbers (design/rd-probe): 45 lexer states, 5 longer choice points with 57 states; it counted 32
        # one-token points because it wrote the body of `gap`'s '+' twice (one copy per first pass), this writes it once
        self.assertEqual((len(dfa.accept), plan.one_token, plan.longer, plan.longer_states), (45, 31, 5, 57))


class Refusals(unittest.TestCase):
    def test_each_planted_grammar_refused_for_its_reason(self) -> None:
        files = sorted(gen.PLANTED.glob("*.g4"))
        self.assertEqual([f.stem for f in files], ["action", "bad-annotation", "left-recursion", "lexer-mode",
                                                    "predicate", "sll-conflict", "state-limit"])
        for path in files:
            with self.subTest(path.name):
                src = path.read_text(encoding="utf-8")
                with self.assertRaises(g4.GrammarError) as caught:
                    gen.build(g4.parse(src, path.name))
                self.assertIn(gen.REFUSED.search(src).group(1), str(caught.exception))
                self.assertRegex(str(caught.exception), rf"^{path.name}:\d+: ")  # names the line

    def test_messages(self) -> None:
        tail = "\nA : 'a' ;\n"
        cases = {
            "s : {p()}? A EOF ;": "t.g4:2: a semantic predicate is not supported",
            "s : A {go();} EOF ;": "t.g4:2: an action is not supported",
            "s : A EOF ;\nB : 'b' -> channel(HIDDEN) ;": "t.g4:3: a lexer command is not supported",
            "s : A EOF ;\nmode X;": "t.g4:3: a lexer mode is not supported",
            "s : x EOF ;\nx : x A | A ;": "t.g4:3: rule x: left recursion (x -> x)",
            "s : x EOF ;\nx : y A | A ;\ny : A? x ;": "t.g4:3: rule x: left recursion (x -> y -> x)",
            "s : (A | A) EOF ;": "t.g4:2: rule s: an SLL conflict: alternatives 1 and 2",
            "s : A* A* EOF ;": "rule s: an SLL conflict",
            "s : (A?)* EOF ;": "rule s: an SLL conflict",
            "s : A EOF ;  // cst: document // cst: block": "t.g4:2: rule s: two tree annotations on one rule",
            "s : A EOF ;\n// cst: list": "t.g4:3: the tree annotation 'cst: list' names no rule",
            "s : b EOF ;": "rule s: unknown rule b",
            "s : 'z' EOF ;": "rule s: the literal 'z' has no token rule of its own",
            "s : A . EOF ;": "the wildcard '.' is not supported",
            "s : x=A EOF ;": "an element label is not supported",
        }
        for src, want in cases.items():
            with self.subTest(src):
                self.assertIn(want, refusal(src + tail))

    def test_recovery_rule_missing(self) -> None:
        g = grammar("s : A EOF ;\nA : 'a' ;\n")
        with self.assertRaises(ValueError):
            cpp.render(*gen.build(g))


class Output(unittest.TestCase):
    def test_annotations_and_hooks(self) -> None:
        g = g4.read(gen.GRAMMAR)
        self.assertEqual(g.cst, {"document": "document", "directive": "directive", "block": "block",
                                 "slicedWord": "slice", "list": "list"})
        text = cpp.render(*gen.build(g))
        self.assertIn("self().open_node(::knobly::node_kind::slice);", text)
        self.assertIn("return b_statements() || self().recover_statements();", text)
        self.assertIn("bool r_nameText() { return b_nameText(); }", text)
        self.assertIn("if (!self().match(tk::end_of_text)) return false;", text)
        for banned in ("throw", "try", "dynamic_cast", "typeid", "#include <vector>", "#include <string>\n"):
            self.assertNotIn(banned, text)

    def test_deterministic_across_hash_seeds(self) -> None:
        script = ("import sys; sys.path.insert(0, sys.argv[1]); import cpp, g4, gen; "
                  "sys.stdout.write(cpp.render(*gen.build(g4.read(gen.GRAMMAR))))")
        outs = {
            subprocess.run([sys.executable, "-c", script, str(HERE)], capture_output=True, text=True, check=True,
                           env={**os.environ, "PYTHONHASHSEED": seed}).stdout
            for seed in ("1", "2", "3")
        }
        self.assertEqual(len(outs), 1)


if __name__ == "__main__":
    unittest.main()
