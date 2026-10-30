// The state every generated handle and snapshot class holds (design.md 2.3, D23; frozen-m1.md section 4.3): one
// pointer to a node whose core carries an intrusive atomic count. Generated classes hold one private
// ::villanelle::detail::view and befriend ::villanelle::detail::access, the hand code's one way to make and read them.
// SKELETON: declarations only; defined in slice 2 (the first layer with handles).
#ifndef VILLANELLE_SUPPORT_VIEW_HPP
#define VILLANELLE_SUPPORT_VIEW_HPP

#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

struct node;  // a graph's or a render's node; each layer's detail/ defines what it holds

class view {
public:
    view() noexcept;
    explicit view(node* target) noexcept;  // takes one count
    view(const view& other) noexcept;
    view& operator=(const view& other) noexcept;
    ~view();
    node* get() const noexcept;
    friend bool operator==(const view& a, const view& b) noexcept;  // identity

private:
    node* node_;
};

struct access;  // defined by the hand code: builds a generated class from a view and reads its view back

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_SUPPORT_VIEW_HPP
