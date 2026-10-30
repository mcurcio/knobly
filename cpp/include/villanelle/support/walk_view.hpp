// villanelle::walk_view<Item>: the range a block's walk returns (codegen 3's walk trait; design.md 2.3, D12;
// frozen-m1.md section 5). Interface frozen by frozen-m2.md 3.1; slice W defines the members (declared only until
// then).
#ifndef VILLANELLE_SUPPORT_WALK_VIEW_HPP
#define VILLANELLE_SUPPORT_WALK_VIEW_HPP

#include <functional>

#include <villanelle/support/config.hpp>
#include <villanelle/support/view.hpp>

VILLANELLE_NAMESPACE_BEGIN

/// An input range over a block's items, depth first; it owns its data, and an edit never invalidates it.
template <class Item>
class walk_view {
public:
    class iterator;
    struct sentinel {};

    iterator begin() const;
    sentinel end() const noexcept;

private:
    detail::view view_;
    std::function<bool(const Item&)> descend_;
    friend struct detail::access;
};

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_SUPPORT_WALK_VIEW_HPP
