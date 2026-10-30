// The state every generated handle and snapshot class holds (design.md 2.3, D23; frozen-m1.md section 4.3): one
// pointer to a node whose core carries an intrusive atomic count. Generated classes hold one private
// ::villanelle::detail::view and befriend ::villanelle::detail::access, the hand code's one way to make and read them.
// Interface frozen by frozen-m2.md section 3.1; the view's members are defined inline here.
#ifndef VILLANELLE_SUPPORT_VIEW_HPP
#define VILLANELLE_SUPPORT_VIEW_HPP

#include <atomic>
#include <cstddef>
#include <cstdlib>
#include <utility>

#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

/// A graph's or a render's node (frozen-m2.md 3.1); each layer's detail/ derives what it holds. The view only counts
/// and compares. Ownership (design.md 2.3): a node either is counted itself (a graph's core, a render, a binding) or
/// lives in a counted node's arena and names it in `counted`, so a view of any node keeps its owner alive, and the
/// owner frees its nodes when it dies (a detached handle's node stays until then). A counted node that lives inside
/// another names it in `outer` (a binding inside its graph): a view takes one count on each node of that chain, so the
/// outer one outlives every view of the inner one. The counts are atomic, so a view may be copied or destroyed on
/// another thread; nothing else is thread-safe (spec 4.1).
struct node {
    node() noexcept = default;
    node(const node&) = delete;
    node& operator=(const node&) = delete;
    virtual ~node() = default;

    /// The node whose count a view of this one takes: itself, or the counted node whose arena holds it.
    node* counted = this;
    /// On a counted node: the counted node whose life must cover its own; null for a root.
    node* outer = nullptr;
    /// On a counted node: how many views (and owners' holds) it has.
    std::atomic<std::size_t> count{0};
};

/// One count on each node of the chain from n's counted owner outward.
inline void retain(node* n) noexcept {
    for (node* at = n == nullptr ? nullptr : n->counted; at != nullptr; at = at->outer) {
        at->count.fetch_add(1, std::memory_order_relaxed);
    }
}

/// Gives back what retain(n) took, innermost first; a node whose count reaches zero is deleted (its outer node is read
/// first).
inline void release(node* n) noexcept {
    for (node* at = n == nullptr ? nullptr : n->counted; at != nullptr;) {
        node* const next = at->outer;
        if (at->count.fetch_sub(1, std::memory_order_acq_rel) == 1) {
            delete at;
        }
        at = next;
    }
}

/// One counted pointer to a node: copying shares it, and the node (with the graph or render it belongs to) lives
/// while any view of it does. Two views are equal when they show the same node (identity, design.md 2.3). Defined
/// here, inline in both modes (frozen-m2.md 3.1 allows it): the count is the hot path of every handle copy.
class view {
public:
    view() noexcept = default;
    explicit view(node* target) noexcept : node_(target) { retain(node_); }  // takes one count
    view(const view& other) noexcept : node_(other.node_) { retain(node_); }
    view(view&& other) noexcept : node_(std::exchange(other.node_, nullptr)) {}
    view& operator=(const view& other) noexcept {
        if (this != &other) {
            retain(other.node_);
            release(node_);
            node_ = other.node_;
        }
        return *this;
    }
    view& operator=(view&& other) noexcept {
        if (this != &other) {
            release(node_);
            node_ = std::exchange(other.node_, nullptr);
        }
        return *this;
    }
    ~view() { release(node_); }
    node* get() const noexcept { return node_; }
    friend bool operator==(const view& a, const view& b) noexcept { return a.node_ == b.node_; }  // identity

private:
    node* node_ = nullptr;
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
