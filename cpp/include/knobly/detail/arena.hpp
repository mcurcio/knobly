// What every layer's nodes share (design.md 2.3; frozen-m2.md 3.1): the arena a counted node keeps its nodes in, and
// the two ways between a node and a generated handle class. The written layer's graph and binding and the rendered
// layer's render each own one arena. Package-internal.
#ifndef KNOBLY_DETAIL_ARENA_HPP
#define KNOBLY_DETAIL_ARENA_HPP

#include <memory>
#include <utility>
#include <vector>

#include <knobly/support/config.hpp>
#include <knobly/support/view.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace detail {

/// The nodes a counted node owns: each names that node as its counted owner, and dies with it.
struct arena {
    explicit arena(node* owner) noexcept : owner_(owner) {}
    template <class T, class... Args>
    T* make(Args&&... args) {
        auto made = std::make_unique<T>(std::forward<Args>(args)...);
        made->counted = owner_;
        T* const raw = made.get();
        nodes_.push_back(std::move(made));
        return raw;
    }

private:
    node* owner_;
    std::vector<std::unique_ptr<node>> nodes_;
};

/// A generated handle class over a node.
template <class Handle>
Handle make_handle(node* n) {
    return access::make<Handle>(view(n));
}

/// The node a handle shows.
template <class Node, class Handle>
Node* node_of(const Handle& handle) noexcept {
    return static_cast<Node*>(access::view_of(handle).get());
}

}  // namespace detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_ARENA_HPP
