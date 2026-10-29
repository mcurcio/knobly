/**
 * The document graph (spec 6.3): the files one load read, the overrides, the read ledger, and the document source
 * it reads through. Everything else (copies, edges, variables, resolutions, diagnostics) is derived from them by
 * `bind`, cached per graph version; every edit, `setOverride` and read bumps the version. Package-internal: programs
 * see IDocumentGraph.
 */

import { DiagnosticCode } from "../diagnostics.js";
import type { IExtension } from "../extension.js";
import type { ILocatedDiagnostic } from "../report.js";
import type { IDocumentSource } from "../source.js";
import { bind, type IBindingWithNeeds, type IOverrideInput, type IReadLedger } from "./bind.js";
import { Document, type IDocumentHost } from "./document.js";
import { SaveError } from "./errors.js";
import type { Bound } from "./expanded.js";
import type { IDocumentWriter, IFileWrite } from "../source.js";
import type { IDocumentEdge, IDocumentGraph, IVariable } from "./model.js";
import { checkOverride, checkOverrideName } from "./override.js";
import { readUnread } from "./read.js";
import { OverrideVariable } from "./statements.js";

/** The codes `render` owns: the graph's `diagnostics` leaves them out, with every E4xxx code (D11). */
const RENDER_CODES: ReadonlySet<string> = new Set([
  DiagnosticCode.UnknownVariable,
  DiagnosticCode.UnknownSnippet,
  DiagnosticCode.SnippetArity,
  DiagnosticCode.TooManyDirectives,
]);

export class DocumentGraph implements IDocumentGraph, IDocumentHost, IReadLedger {
  readonly documents = new Map<string, Document>();
  readonly extensionNames: ReadonlySet<string>;
  private readonly overrideTexts = new Map<string, string>();
  private readonly overrideValues = new Map<string, readonly Bound[]>();
  private readonly overrideVariables = new Map<string, OverrideVariable>();
  /** Per `JSON.stringify([parentPath, spec])`: the paths or the rejection. */
  private readonly resolutions = new Map<string, readonly string[] | Error>();
  /** Per path whose read rejected: the rejection (a read document is in `documents`). */
  private readonly failedReads = new Map<string, Error>();
  private version = 0;
  private cache: { readonly version: number; readonly binding: IBindingWithNeeds } | undefined;
  private rootDocument: Document | undefined;

  /**
   * Each override goes through the check of an override, in order; the first refusal throws.
   * @throws TypeError for a bad override name or a text that is not a string; BadTextError for a refused text
   */
  constructor(
    private readonly source: IDocumentSource,
    readonly extensions: ReadonlyMap<string, IExtension>,
    overrides: Readonly<Record<string, unknown>>,
  ) {
    this.extensionNames = new Set(extensions.keys());
    for (const [name, text] of Object.entries(overrides)) {
      const values = checkOverride(name, text, { member: "load", textParameter: `overrides[${JSON.stringify(name)}]` });
      this.putOverride(name, text as string, values);
    }
  }

  get root(): Document {
    if (this.rootDocument === undefined) throw new Error("the graph has no root yet");
    return this.rootDocument;
  }

  get overrides(): ReadonlyMap<string, string> {
    return this.overrideTexts;
  }

  setOverride(name: string, text: string | undefined): void {
    if (text === undefined) {
      checkOverrideName(name, "setOverride");
      if (!this.overrideTexts.has(name)) return;
      this.overrideTexts.delete(name);
      this.overrideValues.delete(name);
      this.changed();
      return;
    }
    const values = checkOverride(name, text, { member: "setOverride", textParameter: "text" });
    this.putOverride(name, text, values);
    this.changed();
  }

  /** A changed name keeps its place in `overrides`; a new one (or one removed before) goes at the end (6.2). */
  private putOverride(name: string, text: string, values: readonly Bound[]): void {
    this.overrideTexts.set(name, text);
    this.overrideValues.set(name, values);
    if (!this.overrideVariables.has(name)) this.overrideVariables.set(name, new OverrideVariable(name, () => this.binding()));
  }

  async read(): Promise<readonly string[]> {
    return await readUnread(this, this.source);
  }

  /**
   * Hand every document whose `text` differs from its `savedText` to the writer in one batch, in `documents` order;
   * with none, the writer is not called. When the writer resolves, each written document's `savedText` becomes the
   * text handed over (an edit made while the writer ran stays unsaved); when it rejects, no `savedText` changes.
   */
  async save(writer: IDocumentWriter): Promise<readonly string[]> {
    const files: IFileWrite[] = [];
    for (const doc of this.documents.values()) {
      if (doc.text !== doc.savedText) files.push({ resolvedPath: doc.resolvedPath, text: doc.text, savedText: doc.savedText });
    }
    if (files.length === 0) return [];
    try {
      await writer.write(files);
    } catch (error) {
      throw new SaveError(`the writer rejected: ${error instanceof Error ? error.message : String(error)}`, files, error);
    }
    for (const file of files) this.documents.get(file.resolvedPath)?.markSaved(file.text);
    return files.map((file) => file.resolvedPath);
  }

  edges(): readonly IDocumentEdge[] {
    return this.binding().edges;
  }

  unread(): readonly IDocumentEdge[] {
    return this.binding().unread;
  }

  variables(name?: string): readonly IVariable[] {
    const all: IVariable[] = [...this.documents.values()].flatMap((doc) => doc.variables());
    for (const override of this.overrideTexts.keys()) {
      const variable = this.overrideVariables.get(override);
      if (variable !== undefined) all.push(variable);
    }
    return name === undefined ? all : all.filter((v) => v.name === name);
  }

  get diagnostics(): readonly ILocatedDiagnostic[] {
    const found = this.binding().diagnostics.filter((d) => !d.code.startsWith("E4") && !RENDER_CODES.has(d.code));
    return [...this.syntaxDiagnostics(), ...found];
  }

  /** Each document's syntax diagnostics, documents in order, located. */
  syntaxDiagnostics(): ILocatedDiagnostic[] {
    return [...this.documents.values()].flatMap((doc) =>
      doc.syntax.diagnostics.map((d) => ({ code: d.code, message: d.message, place: doc.place(d.span), via: [] })),
    );
  }

  // --- IDocumentHost ---

  binding(): IBindingWithNeeds {
    if (this.cache?.version !== this.version) {
      const overrides = new Map<string, IOverrideInput>();
      for (const [name, values] of this.overrideValues) {
        const variable = this.overrideVariables.get(name);
        if (variable !== undefined) overrides.set(name, { variable, values });
      }
      this.cache = { version: this.version, binding: bind({ root: this.root, extensions: this.extensions, overrides, reads: this }) };
    }
    return this.cache.binding;
  }

  allDocuments(): readonly Document[] {
    return [...this.documents.values()];
  }

  changed(): void {
    this.version++;
  }

  // --- IReadLedger, and what the read loop records ---

  resolved(parentPath: string, spec: string): readonly string[] | Error | undefined {
    return this.resolutions.get(JSON.stringify([parentPath, spec]));
  }

  /** The document read at `resolvedPath`, the rejection, or undefined (the ledger's `read`; the I/O is `read()`). */
  readOf(resolvedPath: string): Document | Error | undefined {
    return this.documents.get(resolvedPath) ?? this.failedReads.get(resolvedPath);
  }

  recordResolved(parentPath: string, spec: string, paths: readonly string[] | Error): void {
    this.resolutions.set(JSON.stringify([parentPath, spec]), paths);
    this.changed();
  }

  /** Record one read: the document made from its text (the root first), or the rejection. */
  recordRead(resolvedPath: string, text: string | Error): Document | undefined {
    this.changed();
    if (text instanceof Error) {
      this.failedReads.set(resolvedPath, text);
      return undefined;
    }
    const doc = new Document(this, resolvedPath, text);
    this.documents.set(resolvedPath, doc);
    this.rootDocument ??= doc;
    return doc;
  }
}
