// villanelle::walk_view<Item>: the range a block's walk returns (codegen 3's walk trait; design.md 2.3, D12;
// frozen-m2.md 3.1). Written once over detail::block_traits<Item>; every member is defined here, so compiled mode's
// explicit instantiations cover it.
#ifndef VILLANELLE_SUPPORT_WALK_VIEW_HPP
#define VILLANELLE_SUPPORT_WALK_VIEW_HPP

#include <cstddef>
#include <functional>
#include <iterator>
#include <optional>
#include <utility>
#include <vector>

#include <villanelle/support/config.hpp>
#include <villanelle/support/sequence.hpp>
#include <villanelle/support/view.hpp>

VILLANELLE_NAMESPACE_BEGIN

template <class Item, class Directive>
class block;

/// An input range over a block's items at any depth: depth first, pre-order. Entering a block takes that block's
/// snapshot; after yielding an item it descends into the item's own block when it has one and descend(item) is true
/// (no predicate: always). It owns its data (views and snapshots), so an edit never invalidates it: an item detached
/// after its block's snapshot is still yielded and not descended, and an item inserted into a block already entered
/// is not visited (design.md 2.3, finding F8).
template <class Item>
class walk_view {
public:
    struct sentinel {};

    class iterator {
    public:
        using value_type = Item;
        using difference_type = std::ptrdiff_t;
        using iterator_concept = std::input_iterator_tag;
        using iterator_category = std::input_iterator_tag;

        iterator() = default;
        Item operator*() const { return frames_.back().items.at(frames_.back().next - 1); }
        /// Descends into the item just yielded when it has a block (and descend allows it), else moves on.
        iterator& operator++() {
            const Item current = **this;
            if (std::optional<detail::view> inner = detail::block_traits<Item>::block_of(current)) {
                if (!descend_ || descend_(current)) {
                    frames_.push_back({detail::block_traits<Item>::items(*inner), 0});
                }
            }
            settle();
            return *this;
        }
        void operator++(int) { ++*this; }
        friend bool operator==(const iterator& it, sentinel) noexcept { return it.frames_.empty(); }

    private:
        friend class walk_view;
        struct frame {
            sequence<Item> items;
            std::size_t next;  // the index after the item last yielded from this block
        };

        iterator(sequence<Item> top, std::function<bool(const Item&)> descend) : descend_(std::move(descend)) {
            frames_.push_back({std::move(top), 0});
            settle();
        }

        /// Steps to the next item of the deepest block that has one, leaving exhausted blocks; empty at the end.
        void settle() {
            while (!frames_.empty() && frames_.back().next >= frames_.back().items.size()) {
                frames_.pop_back();
            }
            if (!frames_.empty()) {
                ++frames_.back().next;
            }
        }

        std::vector<frame> frames_;
        std::function<bool(const Item&)> descend_;
    };

    iterator begin() const { return iterator(detail::block_traits<Item>::items(view_), descend_); }
    sentinel end() const noexcept { return {}; }

private:
    template <class, class>
    friend class block;
    walk_view(detail::view view, std::function<bool(const Item&)> descend)
        : view_(std::move(view)), descend_(std::move(descend)) {}

    detail::view view_;
    std::function<bool(const Item&)> descend_;
    friend struct detail::access;
};

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_SUPPORT_WALK_VIEW_HPP
