"""The highlight generator's own checks, planted: each broken model or grammar must be refused (tools/check.sh runs
this, so a check cannot quietly stop working). Python 3.9+ standard library only."""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen  # noqa: E402


class Planted(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.model = json.loads(gen.MODEL.read_text(encoding="utf-8"))
        self.grammar = gen.GRAMMAR.read_text(encoding="utf-8")

    def refused(self, needle: str) -> None:
        (self.dir / "highlight.json").write_text(json.dumps(self.model), encoding="utf-8")
        (self.dir / "Knobly.g4").write_text(self.grammar, encoding="utf-8")
        with self.assertRaises(gen.ModelError) as e:
            gen.load(self.dir / "Knobly.g4", self.dir / "highlight.json")
        self.assertIn(needle, str(e.exception))

    def test_the_real_model_loads(self) -> None:
        m = gen.load()
        self.assertEqual(set(m.token_class), set(m.tokens))

    def test_a_token_kind_with_no_class(self) -> None:
        del self.model["tokens"]["TILDE"]
        self.refused("no class for the token kinds TILDE")

    def test_a_token_the_grammar_lacks(self) -> None:
        self.model["tokens"]["COLON"] = {"class": "punctuation"}
        self.refused("COLON")

    def test_an_unknown_class(self) -> None:
        self.model["tokens"]["WORD"]["class"] = "identifier"
        self.refused("unknown class 'identifier'")

    def test_a_start_token_longer_than_one_character(self) -> None:
        self.model["head"]["starts"].append("COMMENT")
        self.refused("head start COMMENT")

    def test_a_dfa_state_that_does_not_accept(self) -> None:
        # '<<' is a token but '<' is not: the state after one '<' does not accept, so longest match needs lookahead.
        self.grammar = re.sub(r"^TILDE : '~' ;", "TILDE : '~' ; ANGLE : '<<' ;", self.grammar, flags=re.M)
        self.grammar = self.grammar.replace("LBRACE : '{' ; RBRACE", "LBRACE : '{' ; ANGLE : '<<' ; RBRACE")
        self.grammar = self.grammar.replace("[\\]\\-~", "[\\]\\-~<")
        self.model["tokens"]["ANGLE"] = {"class": "punctuation"}
        self.refused("do not accept")

    def test_textmate_patterns_capture_nothing(self) -> None:
        # The statement begin numbers its own groups: a token pattern may hold only non-capturing ones.
        for kind, pattern in gen.token_patterns(gen.load()).items():
            self.assertIsNone(re.search(r"(?<!\\)\((?!\?)", pattern), kind)


if __name__ == "__main__":
    unittest.main()
