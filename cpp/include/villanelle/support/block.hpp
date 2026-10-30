// villanelle::block<Item, Directive>: the one block shape (spec 2.11; design.md 3.1; frozen-m2.md 3.1), written once
// over detail::block_traits<Item>, the hook each layer fills. Every member is defined here, so compiled mode's explicit
// instantiations (implementation.hpp) cover it.
#ifndef VILLANELLE_SUPPORT_BLOCK_HPP
#define VILLANELLE_SUPPORT_BLOCK_HPP

#include <compare>
#include <cstddef>
#include <functional>
#include <iterator>
#include <optional>
#include <string_view>
#include <type_traits>
#include <utility>
#include <vector>

#include <villanelle/detail/raise.hpp>
#include <villanelle/support/config.hpp>
#include <villanelle/support/sequence.hpp>
#include <villanelle/support/view.hpp>
#include <villanelle/support/walk_view.hpp>

VILLANELLE_NAMESPACE_BEGIN

/// Holds a shared reference to its graph or render, never to a block object. Iteration reads one snapshot of the
/// items, taken at begin(): an edit during a loop never invalidates it (design.md 2.3); end() holds no snapshot (an
/// iterator is at an end once its own snapshot is exhausted), and size() and at() read the live block without taking
/// one, so an index loop or an iterator loop that calls end() each time is linear; directives() reads a fresh one.
template <class Item, class Directive>
class block {
public:
    /// A random-access iterator over the snapshot taken at begin(); *it is an Item (a prvalue). Positions count from
    /// the snapshot's end, so an iterator compares equal to end() once its own snapshot is exhausted, whatever an
    /// edit did to the block since.
    class iterator {
    public:
        using value_type = Item;
        using difference_type = std::ptrdiff_t;
        using iterator_concept = std::random_access_iterator_tag;
        using iterator_category = std::input_iterator_tag;  // *it is no reference

        iterator() = default;
        Item operator*() const { return items_.at(static_cast<std::size_t>(at_)); }
        Item operator[](difference_type n) const { return items_.at(static_cast<std::size_t>(at_ + n)); }
        iterator& operator++() noexcept {
            ++at_;
            return *this;
        }
        iterator operator++(int) noexcept {
            iterator before = *this;
            ++at_;
            return before;
        }
        iterator& operator--() noexcept {
            --at_;
            return *this;
        }
        iterator operator--(int) noexcept {
            iterator before = *this;
            --at_;
            return before;
        }
        iterator& operator+=(difference_type n) noexcept {
            at_ += n;
            return *this;
        }
        iterator& operator-=(difference_type n) noexcept {
            at_ -= n;
            return *this;
        }
        friend iterator operator+(iterator it, difference_type n) noexcept { return it += n; }
        friend iterator operator+(difference_type n, iterator it) noexcept { return it += n; }
        friend iterator operator-(iterator it, difference_type n) noexcept { return it -= n; }
        friend difference_type operator-(const iterator& a, const iterator& b) noexcept {
            return b.remaining() - a.remaining();
        }
        friend bool operator==(const iterator& a, const iterator& b) noexcept { return a.remaining() == b.remaining(); }
        friend std::strong_ordering operator<=>(const iterator& a, const iterator& b) noexcept {
            return b.remaining() <=> a.remaining();
        }

    private:
        friend class block;
        iterator(sequence<Item> items, difference_type at) noexcept : items_(std::move(items)), at_(at) {}
        difference_type remaining() const noexcept { return static_cast<difference_type>(items_.size()) - at_; }
        sequence<Item> items_;
        difference_type at_ = 0;
    };

    /// One snapshot of the items, which the iterator holds.
    iterator begin() const { return iterator(traits::items(view_), 0); }
    /// An end of every snapshot (it holds none).
    iterator end() const noexcept { return iterator(); }
    std::size_t size() const { return traits::size(view_); }
    /// @throws villanelle::index_out_of_range when index is not below size()
    Item at(std::size_t index) const {
        const std::size_t size = traits::size(view_);
        if (index >= size) {
            ::villanelle::detail::raise_index_out_of_range(index, size);
        }
        return traits::at(view_, index);
    }
    /// Its directives, in written order.
    sequence<Directive> directives() const { return filtered(std::nullopt); }
    /// Its directives named `name`, in written order.
    sequence<Directive> directives(std::string_view name) const { return filtered(name); }
    /// Every item at any depth, depth first (walk_view).
    walk_view<Item> walk() const { return walk_view<Item>(view_, nullptr); }
    /// Every item at any depth, depth first, entering an item's block only when descend(item) is true.
    walk_view<Item> walk(std::function<bool(const Item&)> descend) const {
        return walk_view<Item>(view_, std::move(descend));
    }

protected:
    block() = default;
    /// A block over its layer's view (an expansion or rendered block is made so; written_block sets view_ itself).
    explicit block(detail::view view) noexcept : view_(std::move(view)) {}
    detail::view view_;
    friend struct detail::access;

private:
    using traits = detail::block_traits<Item>;

    sequence<Directive> filtered(std::optional<std::string_view> name) const {
        static_assert(std::is_same_v<Directive, typename traits::directive>,
                      "a block's Directive is its layer's block_traits<Item>::directive");
        std::vector<Directive> out;
        for (const Item& item : traits::items(view_)) {
            if (std::optional<Directive> directive = traits::as_directive(item, name)) {
                out.push_back(std::move(*directive));
            }
        }
        return out;
    }
};

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_SUPPORT_BLOCK_HPP
