// The written definitions' entry point: <knobly/written.hpp> includes it at its end in header-only mode, and
// <knobly/implementation.hpp> in compiled mode (frozen-m1.md section 5). Every definition here carries
// KNOBLY_API (or is a template, or a package-internal inline used only here). Slice W's port of the TypeScript
// binding's written layer (frozen-m2.md section 4): core.hpp (the nodes), entry.hpp (entry rules), shape.hpp
// (anatomy, shapes, names), edits.hpp (documents and edits), bind.hpp (the binding), host.hpp (the graph's own work),
// then the public members.
#ifndef KNOBLY_DETAIL_WRITTEN_DEFINITIONS_HPP
#define KNOBLY_DETAIL_WRITTEN_DEFINITIONS_HPP

#include <knobly/detail/shared/definitions.hpp>
#include <knobly/detail/written/bind.hpp>
#include <knobly/detail/written/core.hpp>
#include <knobly/detail/written/document.hpp>
#include <knobly/detail/written/edits.hpp>
#include <knobly/detail/written/entry.hpp>
#include <knobly/detail/written/expansion.hpp>
#include <knobly/detail/written/format.hpp>
#include <knobly/detail/written/graph.hpp>
#include <knobly/detail/written/host.hpp>
#include <knobly/detail/written/processor.hpp>
#include <knobly/detail/written/shape.hpp>
#include <knobly/detail/written/statements.hpp>
#include <knobly/detail/written/values.hpp>
#include <knobly/detail/written/variables.hpp>

#endif  // KNOBLY_DETAIL_WRITTEN_DEFINITIONS_HPP
