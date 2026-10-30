// render(graph) (spec 7.0; ts/src/rendered/render.ts): the rendered layer's entry point and the one home of the render
// algorithm. It builds on the written layer's public objects only (graph.expand(), the graph's root path): each
// directive expansion becomes a directive holding the expansion's own objects; it looks no name up, reads no file and
// names nothing (addresses come from rendered::addresses under the caller's key rule).
#ifndef VILLANELLE_DETAIL_RENDERED_RENDER_HPP
#define VILLANELLE_DETAIL_RENDERED_RENDER_HPP

#include <optional>

#include <villanelle/detail/raise.hpp>
#include <villanelle/detail/rendered/nodes.hpp>
#include <villanelle/rendered.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace rendered {

namespace detail {

/// Each directive expansion of `block` as a directive under `parent`, its own block built the same way.
inline block_node* build(render_core* render, const ::villanelle::written::expansion_block& block,
                         directive_node* parent) {
    auto* out = render->nodes.make<block_node>();
    for (const ::villanelle::written::directive_expansion& item : block) {
        const ::villanelle::written::written_directive written = item.written();
        auto* directive = render->nodes.make<directive_node>(written.name(), item.values(), item.unreadable(), parent,
                                                             item.origin(), written);
        if (const std::optional<::villanelle::written::expansion_block> inner = item.block()) {
            directive->block = build(render, *inner, directive);
        }
        out->items.push_back(directive);
    }
    return out;
}

}  // namespace detail

VILLANELLE_API ::villanelle::rendered::rendered render(const ::villanelle::written::document_graph& graph) {
    // The one graph a C++ program can pass that has no callable expand: a handle moved from.
    if (::villanelle::detail::access::view_of(graph).get() == nullptr) {
        ::villanelle::detail::raise(::villanelle::argument_type_error(
            ::villanelle::detail::argument_type_message("render", "graph", "an empty document graph")));
    }
    const ::villanelle::written::expansion expansion = graph.expand();
    const ::villanelle::source_position start(0, 0, 0);
    ::villanelle::directive_origin origin(
        ::villanelle::place(graph.root().resolved_path(), ::villanelle::source_span(start, start)), {});
    auto* core = new detail::render_core(graph, std::move(origin), expansion.unreadable(), expansion.diagnostics());
    // The handle takes the render's count before the build allocates, so a failure frees it.
    ::villanelle::rendered::rendered out = ::villanelle::detail::make_handle<::villanelle::rendered::rendered>(core);
    core->block = detail::build(core, expansion.block(), nullptr);
    return out;
}

}  // namespace rendered

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_RENDERED_RENDER_HPP
