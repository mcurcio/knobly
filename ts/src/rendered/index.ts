/**
 * The rendered layer's public API (spec 7; import path "villanelle/rendered"): `render (graph)` and the rendered
 * tree's types (generated, gen/api/rendered.ts). It builds on the low level's public API; nothing below it imports
 * this module (spec 5, "Layer direction"; checked by ts/eslint.config.js).
 */

export { ChangeKind } from "../gen/api/kinds.js";
export type {
  Added,
  Address,
  AddressStep,
  Change,
  Changed,
  Directive,
  KeyOptions,
  KeyRule,
  Removed,
  Rendered,
  RenderedBlock,
  Unknown,
} from "../gen/api/rendered.js";
export { render } from "./render.js";
