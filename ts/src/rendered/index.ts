/**
 * The rendered layer (spec 7): `render (graph)` and the rendered tree's types. It builds on the low level; nothing
 * below it imports this module (spec 5, "Layer direction"; checked by ts/eslint.config.js).
 */

export { render } from "./render.js";
export {
  type Change,
  ChangeKind,
  type IAdded,
  type IAddress,
  type IAddressStep,
  type IArgument,
  type IChanged,
  type IDirective,
  type IKeyOptions,
  type IRemoved,
  type IRendered,
  type IUnknown,
  type IUnreadable,
  type KeyRule,
  UnreadableReason,
  type WalkControl,
} from "./model.js";
