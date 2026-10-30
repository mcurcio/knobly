// The layer-boundary check bites (spec 7.0; tests/generated/layers_<header>_definitions.cpp): the rendered layer's
// definitions, compiled as that check compiles them, with a render-side function that reaches into the written
// layer's detail types, as a definition in detail/rendered/ might. Building this file must fail; with
// VILLANELLE_CONTROL (the same function through the public written objects only) it must build.
#define VILLANELLE_HEADER_ONLY 0

#include <villanelle/detail/rendered/definitions.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace rendered::detail {

inline bool refused(const ::villanelle::written::document_graph& graph) {
#ifndef VILLANELLE_CONTROL
    return ::villanelle::detail::node_of<::villanelle::written::detail::graph_core>(graph) != nullptr;
#else
    return graph.root().block().size() != 0;
#endif
}

}  // namespace rendered::detail
VILLANELLE_NAMESPACE_END
