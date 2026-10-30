// Documents, copies, edges and the written block (spec 6.4, 6.5, 2.11): the public members over the document's nodes
// (core.hpp) and edits (edits.hpp).
#ifndef VILLANELLE_DETAIL_WRITTEN_DOCUMENT_HPP
#define VILLANELLE_DETAIL_WRITTEN_DOCUMENT_HPP

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <villanelle/detail/raise.hpp>
#include <villanelle/detail/written/core.hpp>
#include <villanelle/detail/written/edits.hpp>
#include <villanelle/detail/written/host.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

namespace detail {

/// A sequence of handles over nodes.
template <class Handle, class Node>
::villanelle::sequence<Handle> handles_of(const std::vector<Node*>& nodes) {
    std::vector<Handle> out;
    out.reserve(nodes.size());
    for (Node* n : nodes) {
        out.push_back(make_handle<Handle>(n));
    }
    return out;
}

/// The edges whose targets include `path`, in walk order.
inline std::vector<edge_node*> edges_into(graph_core* graph, const std::string& path) {
    std::vector<edge_node*> out;
    for (edge_node* edge : binding_of(graph)->edges) {
        if (std::find(edge->targets.begin(), edge->targets.end(), path) != edge->targets.end()) {
            out.push_back(edge);
        }
    }
    return out;
}

}  // namespace detail

VILLANELLE_API std::string document::resolved_path() const {
    return detail::node_of<detail::document_node>(*this)->path;
}

VILLANELLE_API std::string document::saved_text() const { return detail::node_of<detail::document_node>(*this)->saved; }

VILLANELLE_API std::string document::text() const { return detail::node_of<detail::document_node>(*this)->parsed.text; }

VILLANELLE_API ::villanelle::syntax::syntax document::syntax() const {
    return detail::node_of<detail::document_node>(*this)->parsed.syntax;
}

VILLANELLE_API ::villanelle::written::written_block document::block() const {
    return detail::make_handle<::villanelle::written::written_block>(
        detail::node_of<detail::document_node>(*this)->block);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::document_edge> document::included_by() const {
    detail::document_node* doc = detail::node_of<detail::document_node>(*this);
    return detail::handles_of<::villanelle::written::document_edge>(detail::edges_into(doc->graph, doc->path));
}

VILLANELLE_API void document::replace_with_text(::villanelle::config_text text) const {
    detail::replace_document(detail::node_of<detail::document_node>(*this), text.view());
}

VILLANELLE_API ::villanelle::written::copy document_edge::copy() const {
    return detail::make_handle<::villanelle::written::copy>(detail::node_of<detail::edge_node>(*this)->copy);
}

VILLANELLE_API ::villanelle::sequence<std::string> document_edge::specs() const {
    return detail::node_of<detail::edge_node>(*this)->specs;
}

VILLANELLE_API ::villanelle::sequence<std::string> document_edge::targets() const {
    return detail::node_of<detail::edge_node>(*this)->targets;
}

VILLANELLE_API ::villanelle::written::statement copy::statement() const {
    return detail::make_handle<::villanelle::written::statement>(detail::node_of<detail::copy_node>(*this)->statement);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::step> copy::via() const {
    return detail::node_of<detail::copy_node>(*this)->via;
}

/// @throws villanelle::index_out_of_range for an index outside 0..size()
VILLANELLE_API ::villanelle::sequence<::villanelle::written::statement> written_block::insert_statements(
    std::int64_t index, ::villanelle::config_text text) const {
    detail::block_node* block = static_cast<detail::block_node*>(view_.get());
    if (block->owner != nullptr) {
        detail::live(block->owner);
    }
    if (index < 0 || static_cast<std::size_t>(index) > block->handles.size()) {
        ::villanelle::detail::raise(::villanelle::index_out_of_range(
            "statement index " + std::to_string(index) + " is outside 0.." + std::to_string(block->handles.size())));
    }
    return detail::handles_of<::villanelle::written::statement>(
        detail::insert_statements(block, static_cast<std::size_t>(index), text.view()));
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::statement> written_block::add_statements(
    ::villanelle::config_text text) const {
    detail::block_node* block = static_cast<detail::block_node*>(view_.get());
    if (block->owner != nullptr) {
        detail::live(block->owner);
    }
    return insert_statements(static_cast<std::int64_t>(block->handles.size()), std::move(text));
}

}  // namespace written

namespace detail {

/// One snapshot of the block's statements; a detached owner's block raises detached_error.
VILLANELLE_API ::villanelle::sequence<::villanelle::written::statement>
block_traits<::villanelle::written::statement>::items(const view& block) {
    auto* node = static_cast<::villanelle::written::detail::block_node*>(block.get());
    if (node->owner != nullptr) {
        ::villanelle::written::detail::live(node->owner);
    }
    return ::villanelle::written::detail::handles_of<::villanelle::written::statement>(node->handles);
}

VILLANELLE_API std::size_t block_traits<::villanelle::written::statement>::size(const view& block) {
    auto* node = static_cast<::villanelle::written::detail::block_node*>(block.get());
    if (node->owner != nullptr) {
        ::villanelle::written::detail::live(node->owner);
    }
    return node->handles.size();
}

VILLANELLE_API ::villanelle::written::statement block_traits<::villanelle::written::statement>::at(const view& block,
                                                                                                   std::size_t index) {
    auto* node = static_cast<::villanelle::written::detail::block_node*>(block.get());
    if (node->owner != nullptr) {
        ::villanelle::written::detail::live(node->owner);
    }
    return make_handle<::villanelle::written::statement>(node->handles[index]);
}

VILLANELLE_API std::optional<block_traits<::villanelle::written::statement>::directive>
block_traits<::villanelle::written::statement>::as_directive(const ::villanelle::written::statement& item,
                                                             std::optional<std::string_view> name) {
    std::optional<directive> found = item.as<directive>();
    if (found && name && found->name() != *name) {
        return std::nullopt;
    }
    return found;
}

/// The statement's own block; empty when it has none or is detached (a walk does not descend into it).
VILLANELLE_API std::optional<view> block_traits<::villanelle::written::statement>::block_of(
    const ::villanelle::written::statement& item) {
    auto* node = ::villanelle::written::detail::node_of<::villanelle::written::detail::statement_node>(item);
    if (node->detached || node->block == nullptr) {
        return std::nullopt;
    }
    return view(node->block);
}

}  // namespace detail

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_DOCUMENT_HPP
