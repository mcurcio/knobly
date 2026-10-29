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

import type { IPlace, IStep } from "../origin.js";
import type { ILocatedDiagnostic } from "../report.js";
import type { IDocumentWriter } from "../source.js";
import type { VariableKind } from "../gen/api/kinds.js";
import type { ISyntax } from "../syntax/cst.js";

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
   * @throws (rejects) SaveError { files, cause } when the writer rejects
   */
  save(writer: IDocumentWriter): Promise<readonly string[]>;

  /** Every copy of every extension line (an include line), in walk order. */
  edges(): readonly IDocumentEdge[];
  /** The edges naming a spec not resolved or a file not read yet; non-empty means copies and a render lack them. */
  unread(): readonly IDocumentEdge[];
  /** Every variable (with `name`: of that name): `set` and parameters in document order, then overrides in order. */
  variables(name?: string): readonly IVariable[];
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

export type Statement = IWrittenDirective | ISetLine | ISnippetLine | IUseLine | IUnreadableLine;

/** What every statement has. */
export interface IStatementBase {
  readonly document: IDocument;
  /** The statement whose block holds it; undefined at a document's top level. */
  readonly parent: Statement | undefined;
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
}

/** A directive, or (kind "extension") a line whose name a registered extension owns: an include line. */
export interface IWrittenDirective extends IStatementBase {
  readonly kind: "directive" | "extension";
  readonly name: string;
  /** In order. An include line: its path. */
  readonly values: readonly WrittenValue[];
  /** Undefined when written without one. An include line: its `set` lines. */
  readonly block: IWrittenBlock | undefined;
  /**
   * @throws BadTextError: not one WORD, or a name that would change its kind (`set`, `snippet`, `use`, an extension's);
   * TypeError when `name` is not a string
   */
  rename(name: string): void;
  /**
   * Replace its values, first to last, comments between them included, with villanelle text: `d.set(quote("web"))`.
   * Not the language's `set` line: it replaces a statement's values. @throws BadTextError; TypeError when `text` is
   * not a string
   */
  set(text: string): void;
}

/** `set $name value...;`. */
export interface ISetLine extends IStatementBase {
  readonly kind: "set";
  readonly variable: IVariable;
  /** After the `$name`; `set` never touches it. */
  readonly values: readonly WrittenValue[];
  /** Replace its values (not the `$name`). @throws BadTextError, also for an empty text (E5009); TypeError when `text` is not a string */
  set(text: string): void;
}

/** `snippet name $param... { body }`. */
export interface ISnippetLine extends IStatementBase {
  readonly kind: "snippet";
  readonly name: string;
  readonly parameters: readonly IVariable[];
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
  /** Its directive statements (kind "directive"), with `name`: of that name. */
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
  readonly declaration: IVariable | undefined;
  /** One per copy of its statement, in walk order. */
  resolutions(): readonly IReferenceResolution[];
}

/** A `set` line's `$name`, a snippet parameter, or an override. */
export interface IVariable {
  readonly kind: VariableKind;
  readonly name: string;
  /** Its `$name`; undefined for an override. */
  readonly place: IPlace | undefined;
  readonly line: ISetLine | ISnippetLine | undefined;
  /** The references whose `declaration` it is, reached or not, in document order. */
  references(): readonly IReference[];
  /** The resolutions in which it wins, in walk order. */
  wins(): readonly IReferenceResolution[];
  /** The resolutions in which it is shadowed (another wins), in walk order. */
  shadowedAt(): readonly IReferenceResolution[];
  /**
   * Rename its `$name` only (name without `$`). @throws BadTextError (also E5002); NoSetLineError for an override;
   * TypeError when `name` is not a string
   */
  rename(name: string): void;
  /**
   * Replace its `set` line's values. @throws NoSetLineError for a parameter or an override (use `setOverride`);
   * BadTextError; TypeError when `text` is not a string
   */
  set(text: string): void;
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
export interface IReferenceResolution extends IResolution<IVariable> {
  readonly reference: IReference;
  /** The winning `set` line's values, or for a parameter the `use` line's values bound to it; empty for an override or unbound. */
  readonly values: readonly WrittenValue[];
}
