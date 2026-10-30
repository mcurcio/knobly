// The document graph (spec 6.3): documents, overrides, edges, variables, diagnostics, save.
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_WRITTEN_GRAPH_HPP
#define VILLANELLE_DETAIL_WRITTEN_GRAPH_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

VILLANELLE_API ::villanelle::written::document document_graph::root() const {
    ::villanelle::detail::not_built("written::document_graph::root");
}

VILLANELLE_API ::villanelle::ordered_map<std::string, ::villanelle::written::document> document_graph::documents()
    const {
    ::villanelle::detail::not_built("written::document_graph::documents");
}

VILLANELLE_API ::villanelle::ordered_map<std::string, ::villanelle::config_text> document_graph::overrides() const {
    ::villanelle::detail::not_built("written::document_graph::overrides");
}

VILLANELLE_API void document_graph::set_override(std::string_view, std::optional<::villanelle::config_text>) const {
    ::villanelle::detail::not_built("written::document_graph::set_override");
}

VILLANELLE_API ::villanelle::sequence<std::string> document_graph::read() const {
    ::villanelle::detail::not_built("written::document_graph::read");
}

VILLANELLE_API ::villanelle::sequence<std::string> document_graph::save(
    std::shared_ptr<::villanelle::document_writer>) const {
    ::villanelle::detail::not_built("written::document_graph::save");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::document_edge> document_graph::edges() const {
    ::villanelle::detail::not_built("written::document_graph::edges");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::document_edge> document_graph::unread() const {
    ::villanelle::detail::not_built("written::document_graph::unread");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::variable> document_graph::variables() const {
    ::villanelle::detail::not_built("written::document_graph::variables");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::variable> document_graph::variables(
    std::string_view) const {
    ::villanelle::detail::not_built("written::document_graph::variables");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::located_diagnostic> document_graph::diagnostics() const {
    ::villanelle::detail::not_built("written::document_graph::diagnostics");
}

VILLANELLE_API ::villanelle::written::expansion document_graph::expand() const {
    ::villanelle::detail::not_built("written::document_graph::expand");
}

VILLANELLE_API bool operator==(const ::villanelle::written::document_graph&,
                               const ::villanelle::written::document_graph&) {
    ::villanelle::detail::not_built("operator== of document_graph");
}

}  // namespace written

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_GRAPH_HPP
