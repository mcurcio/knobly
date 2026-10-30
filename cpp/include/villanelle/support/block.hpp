// villanelle::block<Item, Directive>: the one block shape (spec 2.11; design.md 3.1; frozen-m1.md section 5).
// SKELETON: declarations only; defined in slice 2.
#ifndef VILLANELLE_SUPPORT_BLOCK_HPP
#define VILLANELLE_SUPPORT_BLOCK_HPP

#include <cstddef>
#include <functional>
#include <string_view>

#include <villanelle/support/config.hpp>
#include <villanelle/support/sequence.hpp>
#include <villanelle/support/view.hpp>
#include <villanelle/support/walk_view.hpp>

VILLANELLE_NAMESPACE_BEGIN

/// Holds a shared reference to its graph or render, never to a block object.
template <class Item, class Directive>
class block {
public:
    class iterator;  // a snapshot of the items, taken at begin()

    iterator begin() const;
    iterator end() const;
    std::size_t size() const;
    Item at(std::size_t index) const;  // index_out_of_range
    sequence<Directive> directives() const;
    sequence<Directive> directives(std::string_view name) const;
    walk_view<Item> walk() const;  // depth first
    walk_view<Item> walk(std::function<bool(const Item&)> descend) const;

protected:
    detail::view view_;
    friend struct detail::access;
};

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_SUPPORT_BLOCK_HPP
