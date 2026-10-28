/**
 * The low level: the config as written, editable, saved back (round 12, design.md §5; slices.md S1 and S2).
 * Types only. Model: ts-morph, a live tree with named edit methods.
 *
 * Handles: one object per written thing for the graph's life (`===` holds); a handle follows its tokens across
 * other edits. A handle whose tokens an edit removed, or whose document's whole text was replaced, is detached:
 * every member but `kind` throws DetachedError.
 *
 * Design rule 1: the texts and the handed-in values are the one source of truth. Copies, edges, variables and
 * resolutions are derived from them when asked; the objects they return (ICopy, IDocumentEdge, IResolution) are
 * snapshots of one derivation, not handles. The only other state is which files were read.
 */

import type { ILocatedDiagnostic } from "../load/report.js";
import type { IPlace, IStep } from "../load/origin.js";
import type { ISyntax } from "../syntax/cst.js";

// --- Files ---

/** The files one load read, and the values the program handed in. */
export interface IDocumentGraph {
  readonly root: IDocument;
  /** Every file read, by resolvedPath, root first, then in first-read order. Never shrinks. */
  readonly documents: ReadonlyMap<string, IDocument>;
  /** Handed-in values by name (without `$`), each as villanelle text. An input of the binding; never saved. */
  readonly handed: ReadonlyMap<string, string>;
  /**
   * Add, change or (with undefined) remove one handed-in value, without a reload.
   * @throws BadTextError when `text` is not one or more values without a `$name` (located in `text`)
   * @throws TypeError when `name` is not letters, digits and `_`
   */
  setHanded(name: string, text: string | undefined): void;

  /** Every copy of every extension line (an include line), in walk order. */
  edges(): readonly IDocumentEdge[];
  /** The edges naming a spec not resolved or a file not read yet; non-empty means copies and `render` lack them. */
  unread(): readonly IDocumentEdge[];
  /** Every variable (with `name`: of that name): `set` and parameters in document order, then handed-in ones. */
  variables(name?: string): readonly IVariable[];
  /**
   * Each document's syntax diagnostics (documents in order), then what the binding found, in walk order, except
   * the codes `render` owns (E4xxx, E5001, E5003, E5004, E5008).
   */
  diagnostics(): readonly ILocatedDiagnostic[];
}

/** One file as written. */
export interface IDocument {
  readonly resolvedPath: string;
  /** As read, or as last handed to a writer that resolved. */
  readonly source: string;
  /** Now. Differs from `source` exactly when the document has unsaved changes. */
  readonly text: string;
  /** Tier 1 of `text`: tokens, lossless tree, syntax diagnostics. */
  readonly syntax: ISyntax;
  readonly body: IWrittenBlock;
  /** The include copies that splice it in; empty for the root and for a file no include reaches now. */
  includedBy(): readonly IDocumentEdge[];
  /**
   * Replace the whole text (undo, a formatter). Takes any text, broken or not. Every handle into the document
   * detaches (the document's own handle stays); `source` is untouched.
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
   * @throws BadTextError
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
  /** @throws BadTextError: not one WORD, or a name that would change its kind (`set`, `snippet`, `use`, an extension's) */
  rename(name: string): void;
  /** Replace its values, first to last, comments between them included. @throws BadTextError */
  setValues(text: string): void;
}

/** `set $name value...;`. */
export interface ISetLine extends IStatementBase {
  readonly kind: "set";
  readonly variable: IVariable;
  /** After the `$name`; `setValues` never touches it. */
  readonly values: readonly WrittenValue[];
  /** @throws BadTextError, also for an empty text (E5009) */
  setValues(text: string): void;
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
  /** @throws BadTextError */
  setValues(text: string): void;
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
   * inner lines keep their own relative indentation. @throws BadTextError; RangeError for an index out of range
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
   * handle detaches. @throws BadTextError (a slice bound takes exactly one word or `$name`)
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

/** A `set` line's `$name`, a snippet parameter, or a handed-in value. */
export interface IVariable {
  readonly kind: "set" | "parameter" | "handed";
  readonly name: string;
  /** Its `$name`; undefined when handed in. */
  readonly place: IPlace | undefined;
  readonly line: ISetLine | ISnippetLine | undefined;
  /** The references whose `declaration` it is, reached or not, in document order. */
  references(): readonly IReference[];
  /** The resolutions in which it wins, in walk order. */
  reaches(): readonly IReferenceResolution[];
  /** The resolutions in which it is overridden (another wins), in walk order. */
  overridden(): readonly IReferenceResolution[];
  /** Rename its `$name` only (name without `$`). @throws BadTextError (also E5002); NoSetLineError when handed */
  rename(name: string): void;
  /** Its `set` line's values. @throws NoSetLineError for a parameter or a handed-in value; BadTextError */
  setValues(text: string): void;
}

/** At one copy: what a written name reads, and what it wins over. */
export interface IResolution<TDefinition> {
  readonly copy: ICopy;
  /** Undefined: nothing of that name is visible there (render reports E5001 or E5003). */
  readonly winner: TDefinition | undefined;
  /** Every other definition visible there, next first (the one that would win if the winner were gone). */
  readonly overridden: readonly TDefinition[];
}

/** A `$name` at one copy. It renders to all of `values`: `set $ports 8080 443;` gives two, replaced together. */
export interface IReferenceResolution extends IResolution<IVariable> {
  readonly reference: IReference;
  /** The winning `set` line's values, or for a parameter the `use` line's values bound to it; empty when handed or unbound. */
  readonly values: readonly WrittenValue[];
}

// --- Saving ---

/** One file a save hands to the writer. */
export interface IFileWrite {
  readonly resolvedPath: string;
  /** What to write. */
  readonly text: string;
  /** The document's `source`: compare it with the disk to find a lost update. */
  readonly source: string;
}

/** The program's writer. The core does no I/O. */
export interface IDocumentWriter {
  /**
   * One batch: stage every file, then commit them together. Rejecting while staging means nothing was committed; a
   * writer that can fail part way through committing (the fs writer's renames, the fetch writer's requests) leaves
   * the files it committed changed on disk while their `source` stays the old text, so the next save refuses them as
   * lost updates until the program reloads (stated cost, D-F1-10).
   */
  write(files: readonly IFileWrite[]): Promise<void>;
}
