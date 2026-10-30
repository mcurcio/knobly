// The rendered layer's nodes (design.md 2.3; frozen-m2.md 3.1, 6): what each rendered handle's view points at. A
// render is a counted node; its blocks and directives live in its arena and name it as their counted owner, so a view
// of any directive keeps the whole render alive, and the render holds the graph handle and the expansion's objects
// (spec 7.0: nothing is copied), so it keeps the graph alive too. A change is a counted node of its own, holding the
// two renders' directives it names. Package-internal: programs see the generated classes (rendered.hpp).
#ifndef KNOBLY_DETAIL_RENDERED_NODES_HPP
#define KNOBLY_DETAIL_RENDERED_NODES_HPP

#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <knobly/detail/arena.hpp>
#include <knobly/rendered.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace rendered::detail {

using ::knobly::detail::node;

struct directive_node;

/// A rendered block's directives (the top level's or a directive's): fixed once the render is built.
struct block_node : node {
    std::vector<directive_node*> items;
};

/// One directive expansion as a rendered directive: its name read once, and the expansion's own objects.
struct directive_node : node {
    directive_node(std::string directive_name, ::knobly::sequence<::knobly::written::expanded_value> its_values,
                   ::knobly::sequence<::knobly::written::unreadable_expansion> its_unreadable,
                   directive_node* enclosing, ::knobly::directive_origin its_origin,
                   ::knobly::written::written_directive its_written)
        : name(std::move(directive_name)),
          values(std::move(its_values)),
          unreadable(std::move(its_unreadable)),
          parent(enclosing),
          origin(std::move(its_origin)),
          written(std::move(its_written)) {}
    std::string name;
    ::knobly::sequence<::knobly::written::expanded_value> values;
    ::knobly::sequence<::knobly::written::unreadable_expansion> unreadable;
    directive_node* parent;
    ::knobly::directive_origin origin;
    ::knobly::written::written_directive written;
    block_node* block = nullptr;  // null: written without a block
};

/// One render: the top-level block and what the expansion said about the whole graph.
struct render_core : node {
    render_core(::knobly::written::document_graph from, ::knobly::directive_origin root_origin,
                ::knobly::sequence<::knobly::written::unreadable_expansion> top_unreadable,
                ::knobly::sequence<::knobly::located_diagnostic> all_diagnostics)
        : graph(std::move(from)),
          origin(std::move(root_origin)),
          unreadable(std::move(top_unreadable)),
          diagnostics(std::move(all_diagnostics)) {}
    ::knobly::detail::arena nodes{this};
    ::knobly::written::document_graph graph;
    ::knobly::directive_origin origin;
    ::knobly::sequence<::knobly::written::unreadable_expansion> unreadable;
    ::knobly::sequence<::knobly::located_diagnostic> diagnostics;
    block_node* block = nullptr;
};

/// One change of a diff: its kind, its address and the directives it names (before, after or both).
struct change_node : node {
    change_node(::knobly::change_kind which, ::knobly::rendered::address at,
                std::optional<::knobly::rendered::directive> was, std::optional<::knobly::rendered::directive> is)
        : kind(which), address(std::move(at)), before(std::move(was)), after(std::move(is)) {}
    ::knobly::change_kind kind;
    ::knobly::rendered::address address;
    std::optional<::knobly::rendered::directive> before;
    std::optional<::knobly::rendered::directive> after;
};

}  // namespace rendered::detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_RENDERED_NODES_HPP
