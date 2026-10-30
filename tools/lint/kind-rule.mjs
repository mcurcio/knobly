// The kind lint for TypeScript (bead vil-umh.11; owner, 2026-10-29, "Yes, generate both"; spec 2.10): a `.kind`,
// `.reason` or `.code` is compared with a generated member (`StatementKind.Set`, `UnreadableReason.Value`,
// `DiagnosticCode.UnknownVariable`), never with a string literal, so a renamed or misspelled value fails to compile
// instead of comparing false. ts/eslint.config.js imports it (`import { KIND_RULE } from "../tools/lint/kind-rule.mjs"`) and spreads it into `no-restricted-syntax`; its Python twin is
// tools/lint/kind_lint.py. One home for the rule; spec/codegen.md section 7 states it.
const MESSAGE = "Compare .kind, .reason and .code with a generated member (StatementKind.Set), never a string literal (spec 2.10).";

/** `no-restricted-syntax` entries (esquery selectors). */
export const KIND_RULE = [
  { selector: "BinaryExpression[operator=/^[!=]==?$/][left.property.name=/^(kind|reason|code)$/][right.type='Literal']", message: MESSAGE },
  { selector: "BinaryExpression[operator=/^[!=]==?$/][right.property.name=/^(kind|reason|code)$/][left.type='Literal']", message: MESSAGE },
  { selector: "SwitchStatement[discriminant.property.name=/^(kind|reason|code)$/] > SwitchCase > Literal.test", message: MESSAGE },
];
