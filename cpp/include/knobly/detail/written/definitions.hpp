// The written definitions' entry point: <villanelle/written.hpp> includes it at its end in header-only mode, and
// <villanelle/implementation.hpp> in compiled mode (frozen-m1.md section 5). Every definition here carries
// VILLANELLE_API (or is a template, or a package-internal inline used only here). Slice W's port of the TypeScript
// binding's written layer (frozen-m2.md section 4): core.hpp (the nodes), entry.hpp (entry rules), shape.hpp
// (anatomy, shapes, names), edits.hpp (documents and edits), bind.hpp (the binding), host.hpp (the graph's own work),
// then the public members.
#ifndef VILLANELLE_DETAIL_WRITTEN_DEFINITIONS_HPP
#define VILLANELLE_DETAIL_WRITTEN_DEFINITIONS_HPP

#include <villanelle/detail/shared/definitions.hpp>
#include <villanelle/detail/written/bind.hpp>
#include <villanelle/detail/written/core.hpp>
#include <villanelle/detail/written/document.hpp>
#include <villanelle/detail/written/edits.hpp>
#include <villanelle/detail/written/entry.hpp>
#include <villanelle/detail/written/expansion.hpp>
#include <villanelle/detail/written/format.hpp>
#include <villanelle/detail/written/graph.hpp>
#include <villanelle/detail/written/host.hpp>
#include <villanelle/detail/written/processor.hpp>
#include <villanelle/detail/written/shape.hpp>
#include <villanelle/detail/written/statements.hpp>
#include <villanelle/detail/written/values.hpp>
#include <villanelle/detail/written/variables.hpp>

#endif  // VILLANELLE_DETAIL_WRITTEN_DEFINITIONS_HPP
