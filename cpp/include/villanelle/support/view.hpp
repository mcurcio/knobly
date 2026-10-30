// The state every generated handle and snapshot class holds (design.md 2.3, D23; frozen-m1.md section 4.3): one
// pointer to a node whose core carries an intrusive atomic count. Generated classes hold one private
// ::villanelle::detail::view and befriend ::villanelle::detail::access, the hand code's one way to make and read them.
// Interface frozen by frozen-m2.md section 3.1. The view's members are VILLANELLE_API: stubs in
// detail/shared/definitions.hpp until slice W defines them (there, or inline here).
#ifndef VILLANELLE_SUPPORT_VIEW_HPP
#define VILLANELLE_SUPPORT_VIEW_HPP

#include <cstdlib>
#include <utility>

#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

/// A graph's or a render's node; each layer's detail/ defines what it holds (frozen-m2.md 3.1). The view only counts
/// and compares.
struct node;

/// One counted pointer to a node: copying shares it, and the node (with the graph or render it belongs to) lives
/// while any view of it does. Two views are equal when they show the same node (identity, design.md 2.3).
class view {
public:
    VILLANELLE_API view() noexcept;
    VILLANELLE_API explicit view(node* target) noexcept;  // takes one count
    VILLANELLE_API view(const view& other) noexcept;
    VILLANELLE_API view(view&& other) noexcept;
    VILLANELLE_API view& operator=(const view& other) noexcept;
    VILLANELLE_API view& operator=(view&& other) noexcept;
    VILLANELLE_API ~view();
    VILLANELLE_API node* get() const noexcept;
    friend VILLANELLE_API bool operator==(const view& a, const view& b) noexcept;  // identity

private:
    node* node_;
};

/// The hand code's one way to build a generated handle from a view and to read a handle's view back. Generated code
/// (each union's as<V>() and visit(f)) uses it too, so it is defined here, before every generated class.
struct access {
    template <class T>
    static T make(view v) noexcept {
        return T(std::move(v));
    }
    template <class T>
    static const view& view_of(const T& handle) noexcept {
        return handle.view_;
    }
};

/// What villanelle::block<Item, Directive> and walk_view<Item> read from their layer (frozen-m2.md 3.1): the one
/// shape's members are written once, in support/block.hpp and support/walk_view.hpp, over these hooks. Each layer
/// specializes it for its item type in its detail/<layer>/templates.hpp (included in both modes), declaring every
/// member VILLANELLE_API static and defining it with the layer's definitions:
///
///     template <> struct block_traits<written::statement> {
///         using directive = written::written_directive;  // the block's Directive
///         // Its items in written order: one snapshot, taken when asked (design.md 2.3, edits during iteration).
///         VILLANELLE_API static sequence<written::statement> items(const view& block);
///         // The item as one of the block's directives, of `name` when given; empty otherwise.
///         VILLANELLE_API static std::optional<directive> as_directive(const written::statement& item,
///                                                                     std::optional<std::string_view> name);
///         // The item's own block, which a walk descends into; empty when it has none (or is detached).
///         VILLANELLE_API static std::optional<view> block_of(const written::statement& item);
///     };
///
/// Specialized for written::statement and written::directive_expansion (slice W) and rendered::directive (slice R).
template <class Item>
struct block_traits;

/// A union's visit(f) met a kind none of its variants has: a broken node, never a program's error.
[[noreturn]] inline void bad_kind() noexcept { std::abort(); }

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_SUPPORT_VIEW_HPP
