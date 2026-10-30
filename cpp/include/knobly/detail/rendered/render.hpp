// render(graph) (spec 7.0; ts/src/rendered/render.ts): the rendered layer's entry point and the one home of the render
// algorithm. It builds on the written layer's public objects only (graph.expand(), the graph's root path): each
// directive expansion becomes a directive holding the expansion's own objects; it looks no name up, reads no file and
// names nothing (addresses come from rendered::addresses under the caller's key rule).
#ifndef KNOBLY_DETAIL_RENDERED_RENDER_HPP
#define KNOBLY_DETAIL_RENDERED_RENDER_HPP

#include <optional>

#include <knobly/detail/raise.hpp>
#include <knobly/detail/rendered/nodes.hpp>
#include <knobly/rendered.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace rendered {

namespace detail {

/// Each directive expansion of `block` as a directive under `parent`, its own block built the same way.
inline block_node* build(render_core* render, const ::knobly::written::expansion_block& block, directive_node* parent) {
    auto* out = render->nodes.make<block_node>();
    for (const ::knobly::written::directive_expansion& item : block) {
        const ::knobly::written::written_directive written = item.written();
        auto* directive = render->nodes.make<directive_node>(written.name(), item.values(), item.unreadable(), parent,
                                                             item.origin(), written);
        if (const std::optional<::knobly::written::expansion_block> inner = item.block()) {
            directive->block = build(render, *inner, directive);
        }
        out->items.push_back(directive);
    }
    return out;
}

}  // namespace detail

KNOBLY_API ::knobly::rendered::rendered render(const ::knobly::written::document_graph& graph) {
    const ::knobly::written::expansion expansion = graph.expand();
    const ::knobly::source_position start(0, 0, 0);
    ::knobly::directive_origin origin(
        ::knobly::place(graph.root().resolved_path(), ::knobly::source_span(start, start)), {});
    auto* core = new detail::render_core(graph, std::move(origin), expansion.unreadable(), expansion.diagnostics());
    // The handle takes the render's count before the build allocates, so a failure frees it.
    ::knobly::rendered::rendered out = ::knobly::detail::make_handle<::knobly::rendered::rendered>(core);
    core->block = detail::build(core, expansion.block(), nullptr);
    return out;
}

}  // namespace rendered

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_RENDERED_RENDER_HPP
