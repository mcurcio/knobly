#!/usr/bin/env bash
# Soundness checks for grammar/Villanelle.g4. Exits non-zero on any failure.
#   1. The parser rules, translated to Bison, have 0 conflicts (proves the grammar unambiguous).
#   2. No two token kinds can match the same text, and no two tokens the parser places side by side lex as one
#      longer token (tools/g4overlap.py: overlap, then longest-match adjacency).
#   3. Each planted bad grammar in tools/planted/ is caught by the Bison check, and each in tools/planted-tokens/ by
#      the token check (the checks still bite).
#   4. spec/schema/ is consistent and generates both bindings' API lists (tools/gen-api.py --check).
#   5. The shared conformance driver's own test (conformance/driver/test_driver.py; spec/conformance.md).
# The public-name check runs in each package's tests (ts/src/api-names.test.ts, py/tests/test_api_names.py).
# Needs: python3, bison, uv (for interegular).
set -u
cd "$(dirname "$0")/.."
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
fail=0

bison_check() {  # $1 = grammar; returns 0 if translated and conflict-free
  python3 tools/g4bison.py "$1" > "$tmp/g.y" 2> "$tmp/err" || return 2
  bison -o "$tmp/g.tab.c" "$tmp/g.y" > "$tmp/bison" 2>&1
}

if bison_check grammar/Villanelle.g4; then echo "ok   grammar: 0 conflicts"
else echo "FAIL grammar: $(cat "$tmp/err" "$tmp/bison" 2>/dev/null)"; fail=1; fi

if uv run -q --with interegular python tools/g4overlap.py grammar/Villanelle.g4 > "$tmp/ov" 2>&1
then echo "ok   tokens: $(tail -2 "$tmp/ov" | paste -sd ";" -)"
else echo "FAIL tokens: $(cat "$tmp/ov")"; fail=1; fi

for f in tools/planted/*.g4; do
  if bison_check "$f"; then echo "FAIL planted $(basename "$f"): not caught"; fail=1
  else echo "ok   planted $(basename "$f"): caught"; fi
done
for f in tools/planted-tokens/*.g4; do
  if uv run -q --with interegular python tools/g4overlap.py "$f" > /dev/null 2>&1; then
    echo "FAIL planted $(basename "$f"): not caught"; fail=1
  else echo "ok   planted $(basename "$f"): caught"; fi
done
if python3 tools/gen-api.py --check > "$tmp/api" 2>&1; then echo "ok   api schema: generates ts and py"
else echo "FAIL api schema: $(cat "$tmp/api")"; fail=1; fi
if python3 conformance/driver/test_driver.py > "$tmp/driver" 2>&1; then echo "ok   conformance driver: self-test"
else echo "FAIL conformance driver: $(cat "$tmp/driver")"; fail=1; fi
exit $fail
