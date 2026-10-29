/**
 * The rendered layer (spec 7): `render (graph)` and the rendered tree's types. It builds on the low level's public
 * API; nothing below it imports this module (spec 5, "Layer direction"; checked by ts/eslint.config.js).
 */

export { render } from "./render.js";
export type {
  Change,
  ChangeKind,
  IAdded,
  IAddress,
  IAddressStep,
  IChanged,
  IDirective,
  IKeyOptions,
  IRemoved,
  IRendered,
  IUnknown,
  KeyRule,
  UnreadableReason,
  WalkControl,
} from "./model.js";
