// render(graph) (spec 7.0; ts/src/rendered/render.ts): the rendered layer's entry point and the one home of the render
// algorithm. It builds on the written layer's public objects only (graph.expand(), the graph's root path): each
// directive expansion becomes a directive holding the expansion's own objects; it looks no name up, reads no file and
// names nothing (addresses come from rendered::addresses under the caller's key rule).
#ifndef KNOBLY_DETAIL_RENDERED_RENDER_HPP
#define KNOBLY_DETAIL_RENDERED_RENDER_HPP

#include <optional>
#include <tuple>
#include <vector>

#include <knobly/detail/raise.hpp>
#include <knobly/detail/rendered/nodes.hpp>
#include <knobly/rendered.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace rendered {

namespace detail {

/// Each directive expansion of `block` as a directive under `parent`, its own block built the same way. A loop over
/// the blocks still to build, not a recursion: the tree may be max_expanded_nesting deep (spec 2.5).
inline block_node* build(render_core* render, const ::knobly::written::expansion_block& block, directive_node* parent) {
    auto* top = render->nodes.make<block_node>();
    std::vector<std::tuple<::knobly::written::expansion_block, directive_node*, block_node*>> tasks{
        {block, parent, top}};
    while (!tasks.empty()) {
        const auto [items, owner, out] = tasks.back();
        tasks.pop_back();
        for (const ::knobly::written::directive_expansion& item : items) {
            const ::knobly::written::written_directive written = item.written();
            auto* directive = render->nodes.make<directive_node>(written.name(), item.values(), item.unreadable(),
                                                                 owner, item.origin(), written);
            if (const std::optional<::knobly::written::expansion_block> inner = item.block()) {
                directive->block = render->nodes.make<block_node>();
                tasks.emplace_back(*inner, directive, directive->block);
            }
            out->items.push_back(directive);
        }
    }
    return top;
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
