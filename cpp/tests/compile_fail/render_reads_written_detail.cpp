// The layer-boundary check bites (spec 7.0; tests/generated/layers_<header>_definitions.cpp): the rendered layer's
// definitions, compiled as that check compiles them, with a render-side function that reaches into the written
// layer's detail types, as a definition in detail/rendered/ might. Building this file must fail; with
// KNOBLY_CONTROL (the same function through the public written objects only) it must build.
#define KNOBLY_HEADER_ONLY 0

#include <knobly/detail/rendered/definitions.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace rendered::detail {

inline bool refused(const ::knobly::written::document_graph& graph) {
#ifndef KNOBLY_CONTROL
    return ::knobly::detail::node_of<::knobly::written::detail::graph_core>(graph) != nullptr;
#else
    return graph.root().block().size() != 0;
#endif
}

}  // namespace rendered::detail
KNOBLY_NAMESPACE_END
