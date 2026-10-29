# Conformance expected-output format, v0

Every binding's `parse` must give these files byte for byte from the same input. The shared driver
([spec/conformance.md](../spec/conformance.md)) sends each case's `src` to the binding's adapter (`parse`), checks the
tree is lossless, prints the result by the rules below and compares it with the expected file.

## Files

- Inputs: `conformance/*.json` (not `conformance/load/`, which has its own format), each a JSON array of `{"name": ..., "src": ...}` cases. A name is unique
  across all of them. `cases.json` and `extra.json` hold the general and recovery cases, `depth.json` the long
  and deeply nested inputs, `edge.json` the alphabet-edge inputs (characters at the edges of what each token
  kind accepts), `tracer.json` the tracer cases (vil-g7n.1.1), and `variables.json` the variable syntax
  (`$name`, a lone `$`, variables touching other values).
- Expected output: one file per case, `conformance/expected/<name>.json`, for every case.

## Content

One JSON object with exactly these keys, in this order:

```
{"tokens":[[kind,text],...],"cst":[kind,start,end,[children...]],"diagnostics":[[code,line,column],...]}
```

- `tokens`: every token of the input in order, as `[kind, text]`. `kind` is the token's name as written in
  `grammar/Villanelle.g4`, in capitals (`WORD`, `SPACE`, `BAD_CHAR`; all 20 are listed in `spec/spec.md` 3.1). Node
  kinds (below) are lowercase. There is no end-of-file token.
- `cst`: the root node, as `[kind, start, end, children]`. `kind` is a CST node kind (`document`,
  `directive`, `block`, `list`, `slice`, `error`). `start` and `end` are the token range: indices
  into `tokens`, half-open. `children` is an array of nodes in the same 4-element form.
- `diagnostics`: `[code, line, column]` per diagnostic, in source order (`spec/spec.md` 3.3). `line` and `column`
  are the 0-based start of the diagnostic's span. The column counts UTF-16 code units. The message
  is not part of the contract.

## Bytes

- No insignificant whitespace.
- Every character above U+007F is written as a lowercase `\uXXXX` escape of its UTF-16 code
  units: an astral character becomes two surrogate escapes, and a lone surrogate is escaped as
  itself. Other characters follow standard JSON escaping (`\n`, `\t`, `\"`, `\\`, `\b`, `\f`,
  `\r`, and a lowercase `\u00xx` for the remaining control characters).
- The file ends with one `"\n"`.

The driver applies these rules (`conformance/driver/encode.py`); an adapter never writes an expected file's bytes.

An adapter still reads and writes JSON (the protocol's messages). Requests are ASCII, so the trap is not invalid
UTF-8 but lone surrogates: three syntax cases (`surrogate-*` in `extra.json`) hold them, as `\u` escapes in the
request. A standard JSON library often replaces one with U+FFFD both when decoding the escape and when encoding the
binding's form of it (Go's `encoding/json` does). The adapter must decode `\ud800` into the binding's own form (for
Go, the WTF-8 bytes `ED A0 80`; `spec/spec.md` 2.1) and write it back as `\ud800`
(`spec/conformance.md` 3).
