/**
 * The document graph (round 12 design.md §5; slices.md 2.7, 2.8): the files one load read, the handed-in values,
 * and the read ledger. Everything else (copies, edges, variables, resolutions, diagnostics) is derived from them by
 * `bind`, cached per graph version; every edit, `setHanded` and read bumps the version. Private to the package.
 */

import type { IExtension } from "../load/processor.js";
import type { ILocatedDiagnostic } from "../load/report.js";
import type { Argument } from "../load/tree.js";
import { bind, type IBindingWithNeeds, type IHandedInput, type IReadLedger, readHanded } from "./bind.js";
import { Document, type IDocumentHost } from "./document.js";
import type { IDocumentEdge, IDocumentGraph, IVariable } from "./model.js";
import { HandedVariable } from "./statements.js";

/** The codes `render` owns: the graph's `diagnostics()` leaves them out (D11). */
const RENDER_CODES: ReadonlySet<string> = new Set(["E5001", "E5003", "E5004", "E5008"]);

export class DocumentGraph implements IDocumentGraph, IDocumentHost, IReadLedger {
  readonly documents = new Map<string, Document>();
  readonly extensionNames: ReadonlySet<string>;
  private readonly handedTexts = new Map<string, string>();
  private readonly handedValues = new Map<string, readonly Argument[]>();
  private readonly handedVariables = new Map<string, HandedVariable>();
  /** Per `JSON.stringify([parentPath, spec])`: the paths or the rejection. */
  private readonly resolutions = new Map<string, readonly string[] | Error>();
  /** Per path whose read rejected: the rejection (a read document is in `documents`). */
  private readonly failedReads = new Map<string, Error>();
  private version = 0;
  private cache: { readonly version: number; readonly binding: IBindingWithNeeds } | undefined;
  private rootDocument: Document | undefined;

  /** @throws TypeError for a bad handed-in name or text (PR 3's rule) */
  constructor(
    readonly extensions: ReadonlyMap<string, IExtension>,
    handed: ReadonlyMap<string, string>,
  ) {
    this.extensionNames = new Set(extensions.keys());
    for (const [name, text] of handed) {
      this.handedValues.set(name, readHanded(name, text));
      this.handedTexts.set(name, text);
      this.handedVariables.set(name, new HandedVariable(name, () => this.binding()));
    }
  }

  get root(): Document {
    if (this.rootDocument === undefined) throw new Error("the graph has no root yet");
    return this.rootDocument;
  }

  get handed(): ReadonlyMap<string, string> {
    return this.handedTexts;
  }

  setHanded(name: string, text: string | undefined): void {
    void name;
    void text;
    throw new Error("not implemented: setHanded (slices.md S2)");
  }

  edges(): readonly IDocumentEdge[] {
    return this.binding().edges;
  }

  unread(): readonly IDocumentEdge[] {
    return this.binding().unread;
  }

  variables(name?: string): readonly IVariable[] {
    const all: IVariable[] = [...this.documents.values()].flatMap((doc) => doc.variables());
    all.push(...this.handedVariables.values());
    return name === undefined ? all : all.filter((v) => v.name === name);
  }

  diagnostics(): readonly ILocatedDiagnostic[] {
    const found = this.binding().diagnostics.filter((d) => !d.code.startsWith("E4") && !RENDER_CODES.has(d.code));
    return [...this.syntaxDiagnostics(), ...found];
  }

  /** Each document's syntax diagnostics, documents in order, located. */
  syntaxDiagnostics(): ILocatedDiagnostic[] {
    return [...this.documents.values()].flatMap((doc) =>
      doc.syntax.diagnostics.map((d) => ({ code: d.code, message: d.message, at: doc.place(d.span), via: [] })),
    );
  }

  // --- IDocumentHost ---

  binding(): IBindingWithNeeds {
    if (this.cache?.version !== this.version) {
      const handed = new Map<string, IHandedInput>();
      for (const [name, values] of this.handedValues) {
        const variable = this.handedVariables.get(name);
        if (variable !== undefined) handed.set(name, { variable, values });
      }
      this.cache = { version: this.version, binding: bind({ root: this.root, extensions: this.extensions, handed, reads: this }) };
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

  read(resolvedPath: string): Document | Error | undefined {
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
