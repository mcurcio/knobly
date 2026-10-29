#!/usr/bin/env bash
# Generate the parser for one target language from grammar/Villanelle.g4.
#   bash tools/gen.sh ts   -> ts/src/gen/              (TypeScript, each file prefixed "// @ts-nocheck")
#   bash tools/gen.sh py   -> py/src/villanelle/_gen/  (Python 3, plus an empty __init__.py)
# Then the API lists from spec/schema/ (tools/gen-api.py): ts/src/gen/api/ or py/src/villanelle/_api/.
# Generated code is never committed (owner, 2026-10-23: "Don't commit the generated code, just the source"):
# build and test run this first, and every run regenerates.
# Needs: Java 11+, curl, python3 (3.9+). The ANTLR jar is cached in $ANTLR_JAR_DIR (default ${XDG_CACHE_HOME:-$HOME/.cache}/antlr)
# and verified against the pinned sha256 on every run.
set -euo pipefail
cd "$(dirname "$0")/.."

ANTLR_VERSION=4.13.2
ANTLR_SHA256=eae2dfa119a64327444672aff63e9ec35a20180dc5b8090b7a6ab85125df4d76
ANTLR_URL="https://www.antlr.org/download/antlr-${ANTLR_VERSION}-complete.jar"
GRAMMAR=grammar/Villanelle.g4

die() { echo "gen.sh: $*" >&2; exit 1; }

case "${1:-}" in
  ts) lang=TypeScript; out=ts/src/gen ;;
  py) lang=Python3; out=py/src/villanelle/_gen ;;
  *) die "usage: tools/gen.sh <ts|py>" ;;
esac

sha256() { if command -v sha256sum > /dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }

command -v java > /dev/null || die "java not found (needs Java 11+)"
java_major=$(java -version 2>&1 | sed -nE '1s/.*version "(1\.)?([0-9]+).*/\2/p')
[[ "$java_major" =~ ^[0-9]+$ && "$java_major" -ge 11 ]] || die "needs Java 11+, found: $(java -version 2>&1 | head -1)"

jar_dir="${ANTLR_JAR_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/antlr}"
jar="$jar_dir/antlr-${ANTLR_VERSION}-complete.jar"
if [[ ! -f "$jar" ]]; then
  mkdir -p "$jar_dir"
  part=$(mktemp "$jar.XXXXXX")
  curl -fsSL -o "$part" "$ANTLR_URL" || { rm -f "$part"; die "download failed: $ANTLR_URL"; }
  got=$(sha256 "$part")
  [[ "$got" == "$ANTLR_SHA256" ]] || { rm -f "$part"; die "$ANTLR_URL: sha256 $got, expected $ANTLR_SHA256"; }
  mv "$part" "$jar"
fi
actual=$(sha256 "$jar")
[[ "$actual" == "$ANTLR_SHA256" ]] || die "$jar: sha256 $actual, expected $ANTLR_SHA256 (delete it to re-download)"

# Generate into a temp dir inside the target (ignored by tsc and eslint), then move each file into place, so a
# concurrent run or reader never sees a half-written file.
mkdir -p "$out"
tmp=$(mktemp -d "$out/.tmp.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
java -jar "$jar" -Dlanguage="$lang" -no-listener -no-visitor -Xexact-output-dir -o "$tmp" "$GRAMMAR"
if [[ "$lang" == TypeScript ]]; then
  # antlr4 4.13.2's typings are incomplete: the generated code does not typecheck (206 errors) but runs.
  for f in "$tmp"/*.ts; do { echo "// @ts-nocheck"; cat "$f"; } > "$f.new" && mv "$f.new" "$f"; done
else
  : > "$tmp/__init__.py"
fi
for f in "$tmp"/*; do mv -f "$f" "$out/"; done

# The API lists (diagnostic codes and messages, kind lists, limits) from spec/schema/: spec/codegen.md.
python3 tools/gen-api.py "$1"
