// What C++ refuses at compile time (frozen-m3.md 4; errata R2): render takes a document graph, so rendering one of
// its documents does not compile, where TypeScript and Python raise the argument type error at run time (the
// conformance case render-not-a-graph). Building this file must fail; with VILLANELLE_CONTROL it must build.
#include <villanelle/rendered.hpp>
#include <villanelle/written.hpp>

namespace vr = villanelle::rendered;
namespace vw = villanelle::written;

vr::rendered refused(const vw::document_graph& graph) {
#ifndef VILLANELLE_CONTROL
    return vr::render(graph.root());
#else
    return vr::render(graph);
#endif
}
