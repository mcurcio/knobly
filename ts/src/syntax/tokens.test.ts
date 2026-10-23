import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { TokenKind } from "./tokens.js";

const GRAMMAR = new URL("../../../grammar/Villanelle.g4", import.meta.url);

/** The grammar's token names: every lexer rule that is not a fragment (several rules may share a line). */
function grammarTokenNames(): string[] {
  const text = readFileSync(GRAMMAR, "utf8");
  return [...text.matchAll(/(?:^|;)\s*([A-Z][A-Z_]*)\s*:/gm)].map((m) => m[1] ?? "");
}

describe("TokenKind", () => {
  it("names exactly the grammar's tokens", () => {
    expect(Object.values(TokenKind).sort()).toEqual(grammarTokenNames().sort());
  });
});
