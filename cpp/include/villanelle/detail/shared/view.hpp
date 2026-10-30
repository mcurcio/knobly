// The view's members (support/view.hpp; design.md 2.3): the intrusive count and identity every handle rests on.
// STUBS (frozen-m2.md): each body is not_built until slice W defines it (here, or inline in support/view.hpp).
#ifndef VILLANELLE_DETAIL_SHARED_VIEW_HPP
#define VILLANELLE_DETAIL_SHARED_VIEW_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/support/view.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

VILLANELLE_API view::view() noexcept : node_(nullptr) {}
VILLANELLE_API view::view(node* target) noexcept : node_(target) { not_built("detail::view::view(node*)"); }
VILLANELLE_API view::view(const view& other) noexcept : node_(other.node_) {}
VILLANELLE_API view::view(view&& other) noexcept : node_(other.node_) { other.node_ = nullptr; }
VILLANELLE_API view& view::operator=(const view& other) noexcept {
    node_ = other.node_;
    return *this;
}
VILLANELLE_API view& view::operator=(view&& other) noexcept {
    node_ = other.node_;
    other.node_ = nullptr;
    return *this;
}
VILLANELLE_API view::~view() = default;
VILLANELLE_API node* view::get() const noexcept { return node_; }
VILLANELLE_API bool operator==(const view& a, const view& b) noexcept { return a.node_ == b.node_; }

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_SHARED_VIEW_HPP
