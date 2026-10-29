/**
 * The rendered layer (spec 7): `render (graph)` and the rendered tree's types. It builds on the low level's public
 * API; nothing below it imports this module (spec 5, "Layer direction"; checked by ts/eslint.config.js).
 */

export { render } from "./render.js";
export type {
  Argument,
  Change,
  ChangeKind,
  IAdded,
  IAddress,
  IAddressStep,
  IArgumentLinks,
  IChanged,
  IDirective,
  IIndexArgument,
  IKeyOptions,
  IListArgument,
  IRemoved,
  IRendered,
  ISliceArgument,
  IStringArgument,
  IUnknown,
  IUnreadable,
  IWordArgument,
  KeyRule,
  UnreadableReason,
  WalkControl,
} from "./model.js";
