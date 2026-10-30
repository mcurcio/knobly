// The rendered layer's nodes (design.md 2.3; frozen-m2.md 3.1, 6): what each rendered handle's view points at. A
// render is a counted node; its blocks and directives live in its arena and name it as their counted owner, so a view
// of any directive keeps the whole render alive, and the render holds the graph handle and the expansion's objects
// (spec 7.0: nothing is copied), so it keeps the graph alive too. A change is a counted node of its own, holding the
// two renders' directives it names. Package-internal: programs see the generated classes (rendered.hpp).
#ifndef VILLANELLE_DETAIL_RENDERED_NODES_HPP
#define VILLANELLE_DETAIL_RENDERED_NODES_HPP

#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <villanelle/detail/arena.hpp>
#include <villanelle/rendered.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace rendered::detail {

using ::villanelle::detail::node;

struct directive_node;

/// A rendered block's directives (the top level's or a directive's): fixed once the render is built.
struct block_node : node {
    std::vector<directive_node*> items;
};

/// One directive expansion as a rendered directive: its name read once, and the expansion's own objects.
struct directive_node : node {
    directive_node(std::string directive_name, ::villanelle::sequence<::villanelle::written::expanded_value> its_values,
                   ::villanelle::sequence<::villanelle::written::unreadable_expansion> its_unreadable,
                   directive_node* enclosing, ::villanelle::directive_origin its_origin,
                   ::villanelle::written::written_directive its_written)
        : name(std::move(directive_name)),
          values(std::move(its_values)),
          unreadable(std::move(its_unreadable)),
          parent(enclosing),
          origin(std::move(its_origin)),
          written(std::move(its_written)) {}
    std::string name;
    ::villanelle::sequence<::villanelle::written::expanded_value> values;
    ::villanelle::sequence<::villanelle::written::unreadable_expansion> unreadable;
    directive_node* parent;
    ::villanelle::directive_origin origin;
    ::villanelle::written::written_directive written;
    block_node* block = nullptr;  // null: written without a block
};

/// One render: the top-level block and what the expansion said about the whole graph.
struct render_core : node {
    render_core(::villanelle::written::document_graph from, ::villanelle::directive_origin root_origin,
                ::villanelle::sequence<::villanelle::written::unreadable_expansion> top_unreadable,
                ::villanelle::sequence<::villanelle::located_diagnostic> all_diagnostics)
        : graph(std::move(from)),
          origin(std::move(root_origin)),
          unreadable(std::move(top_unreadable)),
          diagnostics(std::move(all_diagnostics)) {}
    ::villanelle::detail::arena nodes{this};
    ::villanelle::written::document_graph graph;
    ::villanelle::directive_origin origin;
    ::villanelle::sequence<::villanelle::written::unreadable_expansion> unreadable;
    ::villanelle::sequence<::villanelle::located_diagnostic> diagnostics;
    block_node* block = nullptr;
};

/// One change of a diff: its kind, its address and the directives it names (before, after or both).
struct change_node : node {
    change_node(::villanelle::change_kind which, ::villanelle::rendered::address at,
                std::optional<::villanelle::rendered::directive> was,
                std::optional<::villanelle::rendered::directive> is)
        : kind(which), address(std::move(at)), before(std::move(was)), after(std::move(is)) {}
    ::villanelle::change_kind kind;
    ::villanelle::rendered::address address;
    std::optional<::villanelle::rendered::directive> before;
    std::optional<::villanelle::rendered::directive> after;
};

}  // namespace rendered::detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_RENDERED_NODES_HPP
