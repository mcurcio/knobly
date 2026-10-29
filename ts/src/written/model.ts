/**
 * The low level: the config as written, editable, saved back (round 12, design.md §5; slices.md S1 and S2).
 * Types only. Model: ts-morph, a live tree with named edit methods.
 *
 * Handles: one object per written thing for the graph's life (`===` holds); a handle follows its tokens across
 * other edits. A handle whose tokens an edit removed, or whose document's whole text was replaced, is detached:
 * every member but `kind` throws DetachedError.
 *
 * The low level never imports, names or returns a rendered type (spec 5, "Layer direction"); the rendered layer builds
 * on it through `render (graph)`.
 *
 * Design rule 1: the texts and the overrides are the one source of truth. Copies, edges, variables and
 * resolutions are derived from them when asked; the objects they return (ICopy, IDocumentEdge, IResolution) are
 * snapshots of one derivation, not handles. The only other state is which files were read.
 */

import type { StatementKind, UnreadableReason, ValueKind, VariableKind } from "../gen/api/kinds.js";
import type { IDirectiveOrigin, IPlace, IStep } from "../origin.js";
import type { ILocatedDiagnostic } from "../report.js";
import type { IDocumentWriter } from "../source.js";
import type { ISyntax } from "../syntax/cst.js";
import type { ExpandedValue } from "../value.js";

export type { StatementKind, VariableKind };

// --- Files ---

/**
 * The files one load read, and the overrides the program passed in. It keeps the document source it was loaded
 * through, so it reads (`read`) and saves (`save`) itself; the core still does no I/O.
 */
export interface IDocumentGraph {
  readonly root: IDocument;
  /** Every file read, by resolvedPath, root first, then in first-read order. Never shrinks. */
  readonly documents: ReadonlyMap<string, IDocument>;
  /** The overrides by name (without `$`), each as villanelle text, in order. An input of the binding; never saved. */
  readonly overrides: ReadonlyMap<string, string>;
  /**
   * Each document's syntax diagnostics (documents in order), then what the binding found, in walk order, except
   * the codes `render` reports (E4xxx, E5001, E5003, E5004, E5008).
   */
  readonly diagnostics: readonly ILocatedDiagnostic[];
  /**
   * Add, change or (with undefined) remove one override, without a reload. A changed name keeps its place in
   * `overrides`; a new one goes at the end. Checked by the check of an override, as `load` checks its overrides:
   * `graph.setOverride("host", quote("10.0.60.31"))`.
   * @throws BadTextError when `text` is not one or more values without a `$name` (located in `text`)
   * @throws TypeError when `name` is not letters, digits and `_`, or `text` is neither a string nor undefined
   */
  setOverride(name: string, text: string | undefined): void;
  /**
   * Resolve and read what `unread()` names, through the graph's document source, repeating until nothing new is
   * named; keeps every text and every kept rejection (D12). Returns the resolvedPaths this call read, in read order.
   */
  read(): Promise<readonly string[]>;
  /**
   * Hand every document whose `text` differs from its `savedText` to the writer in one batch, in `documents` order;
   * with none, the writer is not called. When the writer resolves, each written document's `savedText` becomes the
   * text handed over (an edit made while the writer ran stays unsaved); when it rejects, no `savedText` changes (a
   * writer that failed part way through committing: see IDocumentWriter). Returns the resolvedPaths handed over.
   * @throws (rejects) SaveError { paths, cause } when the writer rejects; TypeError when `writer` has no `write`
   * method (before anything is collected)
   */
  save(writer: IDocumentWriter): Promise<readonly string[]>;

  /** Every copy of every extension line (an include line), in walk order. */
  edges(): readonly IDocumentEdge[];
  /** The edges naming a spec not resolved or a file not read yet; non-empty means copies and a render lack them. */
  unread(): readonly IDocumentEdge[];
  /** Every variable (with `name`: of that name): `set` and parameters in document order, then overrides in order. */
  variables(name?: string): readonly Variable[];
  /**
   * The current texts and overrides after expansion (spec 6.10): each directive copy with its values expanded, and
   * what wins over each `$name` there. Pure: reads no file. A snapshot of one working-out of the graph; edit, then
   * call it again for a new one. `render (graph)` builds the rendered tree from it alone.
   */
  expand(): IExpansion;
}

/** One file as written. */
export interface IDocument {
  readonly resolvedPath: string;
  /** As read, or as last handed to a writer that resolved. */
  readonly savedText: string;
  /** Now. Differs from `savedText` exactly when the document has unsaved changes. */
  readonly text: string;
  /** Tier 1 of `text`: tokens, lossless tree, syntax diagnostics. */
  readonly syntax: ISyntax;
  /** Its top-level statements. */
  readonly block: IWrittenBlock;
  /** The include copies that splice it in; empty for the root and for a file no include reaches now. */
  includedBy(): readonly IDocumentEdge[];
  /**
   * Replace the whole text (undo, a formatter). Takes any text, broken or not. Every handle into the document
   * detaches (the document's own handle stays); `savedText` is untouched. @throws TypeError when `text` is not a string
   */
  replaceWithText(text: string): void;
}

/** One copy of an extension line, and the files it matched. */
export interface IDocumentEdge {
  /** `copy.statement` is the include line, editable. */
  readonly copy: ICopy;
  /** The specs the extension gave at this copy, in its order; empty when its values failed. */
  readonly specs: readonly string[];
  /** Every file matched (a glob: several), in splice order; empty when it failed or is unread. */
  readonly targets: readonly string[];
}

/** One place a statement is read. */
export interface ICopy {
  readonly statement: Statement;
  /** The include and `use` steps that bring it there, innermost first; empty at the root. */
  readonly via: readonly IStep[];
}

// --- What is written: discriminated by `kind` ---

/** One statement as written. Narrow by `kind` (spec 6.5); each kind has only the members that can succeed on it. */
export type Statement = IWrittenDirective | IExtensionLine | ISetLine | ISnippetLine | IUseLine | IUnreadableLine;

/** What every statement has. */
export interface IStatementBase {
  readonly kind: StatementKind;
  readonly document: IDocument;
  /** The statement whose block holds it; undefined at a document's top level. */
  readonly parent: IWrittenDirective | IExtensionLine | ISnippetLine | undefined;
  /** From its first owned token to its last (slices.md S1, "Comment ownership"). */
  readonly place: IPlace;
  /** Exact, with the comments it owns; without the indentation before it and the line break after it. */
  readonly text: string;
  /** Every place it is read now, in walk order; empty when no copy reaches it. */
  copies(): readonly ICopy[];
  /**
   * Replace it, and the comments it owns, with zero or more statements. This handle detaches.
   * @throws BadTextError; TypeError when `text` is not a string
   */
  replaceWithText(text: string): readonly Statement[];
  /** Remove it with the comments it owns, and its line when nothing else is on it. Then it is detached. */
  remove(): void;
  /** Insert statements before this one, in its block: `block.insertStatements(indexOf(this), text)`. */
  insertBefore(text: string): readonly Statement[];
  /** Insert statements after this one, in its block: `block.insertStatements(indexOf(this) + 1, text)`. */
  insertAfter(text: string): readonly Statement[];
}

/** A directive. */
export interface IWrittenDirective extends IStatementBase {
  readonly kind: "directive";
  readonly name: string;
  /** In order. */
  readonly values: readonly WrittenValue[];
  /** Undefined when written without one. */
  readonly block: IWrittenBlock | undefined;
  /**
   * @throws BadTextError: not one WORD, or a name that would change its kind (`set`, `snippet`, `use`, an extension's);
   * TypeError when `name` is not a string
   */
  rename(name: string): void;
  /**
   * Replace its values, first to last, comments between them included, with villanelle text: `d.set(quote("web"))`.
   * Not the language's `set` line: it replaces a statement's values. A line break outside a list is refused (it
   * would end the statement). @throws BadTextError; TypeError when `text` is not a string
   */
  set(text: string): void;
}

/** A line whose name a registered extension owns: an include line. Its name is the extension's, so it has no `rename`. */
export interface IExtensionLine extends IStatementBase {
  readonly kind: "extension";
  readonly name: string;
  /** In order. An include line: its path. */
  readonly values: readonly WrittenValue[];
  /** Undefined when written without one. An include line: its `set` lines. */
  readonly block: IWrittenBlock | undefined;
  /** Replace its values, as a directive's `set`. @throws BadTextError; TypeError when `text` is not a string */
  set(text: string): void;
}

/** `set $name value...;`. */
export interface ISetLine extends IStatementBase {
  readonly kind: "set";
  readonly variable: ISetVariable;
  /** After the `$name`; `set` never touches it. */
  readonly values: readonly WrittenValue[];
  /** Replace its values (not the `$name`). @throws BadTextError, also for an empty text (E5009); TypeError when `text` is not a string */
  set(text: string): void;
}

/** `snippet name $param... { body }`. */
export interface ISnippetLine extends IStatementBase {
  readonly kind: "snippet";
  readonly name: string;
  readonly parameters: readonly IParameter[];
  readonly block: IWrittenBlock;
}

/** `use name value...;`. */
export interface IUseLine extends IStatementBase {
  readonly kind: "use";
  readonly snippetName: string;
  /** By where written: a `snippet` line above it in its file; undefined when free. */
  readonly snippet: ISnippetLine | undefined;
  /** Per copy: which snippet the line splices there. */
  snippets(): readonly IResolution<ISnippetLine>[];
  /** Bound to the snippet's parameters by position. */
  readonly values: readonly WrittenValue[];
  /** Replace its values. @throws BadTextError; TypeError when `text` is not a string */
  set(text: string): void;
}

/** A statement that does not parse (R6), a malformed `set`/`snippet`/`use`, or a second `set` of a name in a block. */
export interface IUnreadableLine extends IStatementBase {
  readonly kind: "unreadable";
}

/** The statements of a document or of a block. */
export interface IWrittenBlock {
  /** In order. */
  readonly statements: readonly Statement[];
  /** Its directive statements (kind "directive" only), with `name`: of that name. */
  directives(name?: string): readonly IWrittenDirective[];
  /**
   * Insert statements before `statements[index]` (`index === statements.length` appends), indented as siblings;
   * inner lines keep their own relative indentation. @throws BadTextError; RangeError for an index out of range;
   * TypeError when `text` is not a string
   */
  insertStatements(index: number, text: string): readonly Statement[];
  /** `insertStatements(statements.length, text)`. */
  addStatements(text: string): readonly Statement[];
}

// --- Values: discriminated by `kind` ---

export type WrittenValue = IWord | IString | IList | ISlice | IIndex | IReference;

/** What every written value has. */
export interface IValueBase {
  readonly kind: ValueKind;
  /** Its exact source text. */
  readonly text: string;
  readonly place: IPlace;
  readonly statement: Statement;
  /** The list it is an item of; undefined otherwise. */
  readonly list: IList | undefined;
  /**
   * Replace it with values written as villanelle text: separated by spaces on a line, by commas in a list. This
   * handle detaches. @throws BadTextError (a slice bound takes exactly one word or `$name`); TypeError when `text`
   * is not a string
   */
  replaceWithText(text: string): readonly WrittenValue[];
  /** Remove it (and its separator). Then it is detached. @throws BadTextError when that breaks a rule (a `set` left with no value) */
  remove(): void;
}

export interface IWord extends IValueBase {
  readonly kind: "word";
}

export interface IString extends IValueBase {
  readonly kind: "string";
}

export interface IList extends IValueBase {
  readonly kind: "list";
  readonly items: readonly WrittenValue[];
}

/** `name[start:end]`; either bound may be absent. */
export interface ISlice extends IValueBase {
  readonly kind: "slice";
  readonly name: string;
  readonly start: IWord | IReference | undefined;
  readonly end: IWord | IReference | undefined;
}

/** `name[index]`. */
export interface IIndex extends IValueBase {
  readonly kind: "index";
  readonly name: string;
  readonly index: IWord | IReference;
}

// --- Variables ---

/** One `$name` written as a value. */
export interface IReference extends IValueBase {
  readonly kind: "reference";
  /** Without `$`. */
  readonly name: string;
  /** By where written: the nearest `set` above it in its file, or its snippet's parameter; undefined when free. */
  readonly declaration: ISetVariable | IParameter | undefined;
  /** One per copy of its statement, in walk order. */
  resolutions(): readonly IReferenceResolution[];
}

/** A variable: a `set` line's `$name`, a snippet parameter, or an override. Narrow by `kind` (spec 6.7). */
export type Variable = ISetVariable | IParameter | IOverrideVariable;

/** What every variable has. */
export interface IVariableBase {
  readonly kind: VariableKind;
  readonly name: string;
  /**
   * The references whose `declaration` it is, reached or not, in document order. Lexical only: a `$name` whose
   * declaration is in its own file, found by where it is written. A use in an included file has no declaration (it
   * is resolved per copy), so it is not here: every use, per copy, is in `wins()` and `shadowedAt()`.
   */
  references(): readonly IReference[];
  /** The resolutions in which it wins, in walk order. */
  wins(): readonly IReferenceResolution[];
  /** The resolutions in which it is shadowed (another wins), in walk order. */
  shadowedAt(): readonly IReferenceResolution[];
}

/** A `set` line's `$name`: the same object as that line's `variable`. */
export interface ISetVariable extends IVariableBase {
  readonly kind: "set";
  /** Its `$name`. */
  readonly place: IPlace;
  readonly line: ISetLine;
  /** Rename its `$name` only (name without `$`). @throws BadTextError (also E5002); TypeError when `name` is not a string */
  rename(name: string): void;
  /** Replace its `set` line's values: `line.set(text)`. @throws BadTextError; TypeError when `text` is not a string */
  set(text: string): void;
}

/** A snippet parameter's `$name`. Its value comes from each `use` line: edit those to change it. */
export interface IParameter extends IVariableBase {
  readonly kind: "parameter";
  /** Its `$name`. */
  readonly place: IPlace;
  readonly line: ISnippetLine;
  /** Rename its `$name` only (name without `$`). @throws BadTextError (also E5002); TypeError when `name` is not a string */
  rename(name: string): void;
}

/** An override: written in no file, so it has no place, line, rename or set (change it with `graph.setOverride`). */
export interface IOverrideVariable extends IVariableBase {
  readonly kind: "override";
}

/** At one copy: what a written name reads, and what it wins over. */
export interface IResolution<TDefinition> {
  readonly copy: ICopy;
  /** Undefined: nothing of that name is visible there (render reports E5001 or E5003). */
  readonly winner: TDefinition | undefined;
  /** Every other definition visible there, next first (the one that would win if the winner were gone). */
  readonly shadowed: readonly TDefinition[];
}

/** A `$name` at one copy. It renders to all of `values`: `set $ports 8080 443;` gives two, replaced together. */
export interface IReferenceResolution extends IResolution<Variable> {
  readonly reference: IReference;
  /** The winning `set` line's values, or for a parameter the `use` line's values bound to it; empty for an override or unbound. */
  readonly values: readonly WrittenValue[];
}

// --- The expansion: what `render (graph)` builds on (spec 6.10) ---

/** The graph's current texts and overrides after expansion. A snapshot; its handles are live. */
export interface IExpansion {
  /** The root document's top-level directive copies, includes and uses spliced in place. */
  readonly block: readonly IDirectiveExpansion[];
  /** The top-level statements that cannot be read, in walk order. */
  readonly unreadable: readonly IUnreadableExpansion[];
  /** Syntax diagnostics (documents in order), then everything the expansion found in walk order, render codes included. */
  readonly diagnostics: readonly ILocatedDiagnostic[];
}

/** One copy of a directive, its values expanded at that copy. */
export interface IDirectiveExpansion {
  readonly statement: IWrittenDirective;
  /** Its name's place, and the copy's steps. */
  readonly origin: IDirectiveOrigin;
  readonly values: readonly IValueExpansion[];
  /** Its block's directive copies; undefined when written without a block. */
  readonly block: readonly IDirectiveExpansion[] | undefined;
  /** Its block's statements that cannot be read at this copy. */
  readonly unreadable: readonly IUnreadableExpansion[];
}

/** One copy of a statement that cannot be read there, and why. */
export interface IUnreadableExpansion {
  readonly statement: Statement;
  readonly reason: UnreadableReason;
  /** The statement's own tokens, and the copy's steps. */
  readonly origin: IDirectiveOrigin;
}

/** One value after expansion, with what it was written as and what won over each `$name` on the way. */
export interface IValueExpansion {
  readonly value: ExpandedValue;
  /** The written value on the line it is read in: the `$name` there for a value that came through a variable. */
  readonly written: WrittenValue;
  /** The written value at the end of its chain; undefined for an override. */
  readonly definition: WrittenValue | undefined;
  /** One per variable step of `value.origin.via`, from this value's own line toward where it is written. */
  readonly chain: readonly IReferenceResolution[];
  /** A list's items, expanded the same way; empty for every other kind. */
  readonly items: readonly IValueExpansion[];
}
