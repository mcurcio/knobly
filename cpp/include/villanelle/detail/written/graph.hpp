// The document graph (spec 6.3; ts/src/written/graph.ts): documents, overrides, edges, variables, diagnostics, the
// expansion, read and save, over the graph's core (core.hpp) and its own work (host.hpp).
#ifndef VILLANELLE_DETAIL_WRITTEN_GRAPH_HPP
#define VILLANELLE_DETAIL_WRITTEN_GRAPH_HPP

#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <villanelle/detail/raise.hpp>
#include <villanelle/detail/written/core.hpp>
#include <villanelle/detail/written/document.hpp>
#include <villanelle/detail/written/edits.hpp>
#include <villanelle/detail/written/host.hpp>
#include <villanelle/detail/written/variables.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

namespace detail {

inline graph_core* graph_of(const ::villanelle::written::document_graph& graph) { return node_of<graph_core>(graph); }

}  // namespace detail

VILLANELLE_API ::villanelle::written::document document_graph::root() const {
    return detail::make_handle<::villanelle::written::document>(detail::graph_of(*this)->documents.front());
}

VILLANELLE_API ::villanelle::ordered_map<std::string, ::villanelle::written::document> document_graph::documents()
    const {
    ::villanelle::ordered_map<std::string, ::villanelle::written::document> out;
    for (detail::document_node* doc : detail::graph_of(*this)->documents) {
        out.insert_or_assign(doc->path, detail::make_handle<::villanelle::written::document>(doc));
    }
    return out;
}

VILLANELLE_API ::villanelle::ordered_map<std::string, ::villanelle::config_text> document_graph::overrides() const {
    return detail::graph_of(*this)->override_texts;
}

/// Sets, changes or (with no text) removes one override, through the check of an override.
VILLANELLE_API void document_graph::set_override(std::string_view name,
                                                 std::optional<::villanelle::config_text> text) const {
    detail::graph_core* graph = detail::graph_of(*this);
    if (!text) {
        detail::check_variable_name(name);
        const std::string key(name);
        if (!graph->override_texts.erase(key)) {
            return;
        }
        graph->overrides.erase(key);
        ++graph->version;
        return;
    }
    detail::override_values values = detail::check_override(graph, name, text->view());
    detail::put_override(graph, std::string(name), std::move(*text), std::move(values));
    ++graph->version;
}

VILLANELLE_API ::villanelle::sequence<std::string> document_graph::read() const {
    return detail::read_unread(detail::graph_of(*this));
}

/// @throws villanelle::argument_type_error given no writer
VILLANELLE_API ::villanelle::sequence<std::string> document_graph::save(
    std::shared_ptr<::villanelle::document_writer> writer) const {
    if (!writer) {
        ::villanelle::detail::raise(
            ::villanelle::argument_type_error(::villanelle::detail::argument_type_message("save", "writer", "null")));
    }
    return detail::save(detail::graph_of(*this), *writer);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::document_edge> document_graph::edges() const {
    return detail::handles_of<::villanelle::written::document_edge>(detail::binding_of(detail::graph_of(*this))->edges);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::document_edge> document_graph::unread() const {
    return detail::handles_of<::villanelle::written::document_edge>(
        detail::binding_of(detail::graph_of(*this))->unread);
}

/// Every set line's and snippet line's variables (documents in order, then text order), then the overrides'.
VILLANELLE_API ::villanelle::sequence<::villanelle::written::variable> document_graph::variables() const {
    detail::graph_core* graph = detail::graph_of(*this);
    std::vector<detail::variable_node*> all;
    for (const detail::document_node* doc : graph->documents) {
        detail::variables_of(doc, all);
    }
    for (const auto& [name, text] : graph->override_texts) {
        all.push_back(graph->override_variables.at(name));
    }
    return detail::handles_of<::villanelle::written::variable>(all);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::variable> document_graph::variables(
    std::string_view name) const {
    std::vector<::villanelle::written::variable> out;
    for (const ::villanelle::written::variable& v : variables()) {
        if (v.name() == name) {
            out.push_back(v);
        }
    }
    return out;
}

VILLANELLE_API ::villanelle::sequence<::villanelle::located_diagnostic> document_graph::diagnostics() const {
    return detail::diagnostics_of(detail::graph_of(*this));
}

VILLANELLE_API ::villanelle::written::expansion document_graph::expand() const {
    return detail::make_handle<::villanelle::written::expansion>(detail::expansion_of(detail::graph_of(*this)));
}

}  // namespace written

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_GRAPH_HPP
