// The document graph (spec 6.3; ts/src/written/graph.ts): documents, overrides, edges, variables, diagnostics, the
// expansion, read and save, over the graph's core (core.hpp) and its own work (host.hpp).
#ifndef KNOBLY_DETAIL_WRITTEN_GRAPH_HPP
#define KNOBLY_DETAIL_WRITTEN_GRAPH_HPP

#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <knobly/detail/raise.hpp>
#include <knobly/detail/written/core.hpp>
#include <knobly/detail/written/document.hpp>
#include <knobly/detail/written/edits.hpp>
#include <knobly/detail/written/host.hpp>
#include <knobly/detail/written/variables.hpp>
#include <knobly/written.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace written {

namespace detail {

inline graph_core* graph_of(const ::knobly::written::document_graph& graph) { return node_of<graph_core>(graph); }

}  // namespace detail

KNOBLY_API ::knobly::written::document document_graph::root() const {
    return detail::make_handle<::knobly::written::document>(detail::graph_of(*this)->documents.front());
}

KNOBLY_API ::knobly::ordered_map<std::string, ::knobly::written::document> document_graph::documents() const {
    ::knobly::ordered_map<std::string, ::knobly::written::document> out;
    for (detail::document_node* doc : detail::graph_of(*this)->documents) {
        out.insert_or_assign(doc->path, detail::make_handle<::knobly::written::document>(doc));
    }
    return out;
}

KNOBLY_API ::knobly::ordered_map<std::string, ::knobly::config_text> document_graph::overrides() const {
    return detail::graph_of(*this)->override_texts;
}

/// Sets, changes or (with no text) removes one override, through the check of an override.
KNOBLY_API void document_graph::set_override(std::string_view name, std::optional<::knobly::config_text> text) const {
    detail::graph_core* graph = detail::graph_of(*this);
    if (!text) {
        detail::check_variable_name(name);
        const std::string key(name);
        if (!graph->override_texts.erase(key)) {
            return;
        }
        ++graph->version;
        graph->overrides.erase(key);
        return;
    }
    detail::override_values values = detail::check_override(graph, name, text->view());
    ++graph->version;  // before the change, so one that fails part way never leaves the cached binding in use
    detail::put_override(graph, std::string(name), std::move(*text), std::move(values));
}

KNOBLY_API ::knobly::sequence<std::string> document_graph::read() const {
    return detail::read_unread(detail::graph_of(*this));
}

/// @throws knobly::argument_type_error given no writer
KNOBLY_API ::knobly::sequence<std::string> document_graph::save(
    std::shared_ptr<::knobly::document_writer> writer) const {
    if (!writer) {
        ::knobly::detail::raise(
            ::knobly::argument_type_error(::knobly::detail::argument_type_message("save", "writer", "null")));
    }
    return detail::save(detail::graph_of(*this), *writer);
}

KNOBLY_API ::knobly::sequence<::knobly::written::document_edge> document_graph::edges() const {
    return detail::handles_of<::knobly::written::document_edge>(detail::binding_of(detail::graph_of(*this))->edges);
}

KNOBLY_API ::knobly::sequence<::knobly::written::document_edge> document_graph::unread() const {
    return detail::handles_of<::knobly::written::document_edge>(detail::binding_of(detail::graph_of(*this))->unread);
}

/// Every set line's and snippet line's variables (documents in order, then text order), then the overrides'.
KNOBLY_API ::knobly::sequence<::knobly::written::variable> document_graph::variables() const {
    detail::graph_core* graph = detail::graph_of(*this);
    std::vector<detail::variable_node*> all;
    for (const detail::document_node* doc : graph->documents) {
        detail::variables_of(doc, all);
    }
    for (const auto& [name, text] : graph->override_texts) {
        all.push_back(graph->override_variables.at(name));
    }
    return detail::handles_of<::knobly::written::variable>(all);
}

KNOBLY_API ::knobly::sequence<::knobly::written::variable> document_graph::variables(std::string_view name) const {
    std::vector<::knobly::written::variable> out;
    for (const ::knobly::written::variable& v : variables()) {
        if (v.name() == name) {
            out.push_back(v);
        }
    }
    return out;
}

KNOBLY_API ::knobly::sequence<::knobly::located_diagnostic> document_graph::diagnostics() const {
    return detail::diagnostics_of(detail::graph_of(*this));
}

KNOBLY_API ::knobly::written::expansion document_graph::expand() const {
    return detail::make_handle<::knobly::written::expansion>(detail::expansion_of(detail::graph_of(*this)));
}

}  // namespace written

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_GRAPH_HPP
