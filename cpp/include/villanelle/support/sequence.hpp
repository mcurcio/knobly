// villanelle::sequence<T>: the binding's one list type (design.md 1.3, 2.3; frozen-m1.md section 5).
#ifndef VILLANELLE_SUPPORT_SEQUENCE_HPP
#define VILLANELLE_SUPPORT_SEQUENCE_HPP

#include <compare>
#include <cstddef>
#include <initializer_list>
#include <iterator>
#include <memory>
#include <utility>
#include <vector>

#include <villanelle/detail/raise.hpp>
#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN

/// An immutable, shared list: copying is one pointer; elements come back by value, so nothing it returns can
/// dangle. T may be incomplete where the sequence is declared (a node holds a sequence of nodes).
template <class T>
class sequence {
    using storage = std::shared_ptr<const std::vector<T>>;

public:
    /// A random-access iterator that shares the list it walks; *it is a T (a prvalue). Positions count from its own
    /// list's end, as block's iterator does, so a default-constructed iterator is an end of every list: a type whose
    /// begin() takes a fresh snapshot each call (diagnostics) ends a loop with one that holds none.
    class iterator {
    public:
        using value_type = T;
        using difference_type = std::ptrdiff_t;
        using iterator_concept = std::random_access_iterator_tag;
        using iterator_category = std::input_iterator_tag;  // *it is no reference: C++17's forward iterator needs one

        iterator() = default;
        T operator*() const { return (*items_)[static_cast<std::size_t>(at_)]; }
        T operator[](difference_type n) const { return (*items_)[static_cast<std::size_t>(at_ + n)]; }
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
        friend class sequence;
        iterator(storage items, difference_type at) noexcept : items_(std::move(items)), at_(at) {}
        difference_type remaining() const noexcept {
            return (items_ ? static_cast<difference_type>(items_->size()) : 0) - at_;
        }
        storage items_;
        difference_type at_ = 0;
    };
    using value_type = T;
    using size_type = std::size_t;

    sequence() = default;
    sequence(std::vector<T> items)  // NOLINT(google-explicit-constructor): a vector or a braced list converts
        : items_(std::make_shared<const std::vector<T>>(std::move(items))) {}
    sequence(std::initializer_list<T> items) : sequence(std::vector<T>(items)) {}

    iterator begin() const noexcept { return iterator(items_, 0); }
    iterator end() const noexcept { return iterator(items_, static_cast<std::ptrdiff_t>(size())); }
    std::size_t size() const noexcept { return items_ ? items_->size() : 0; }
    bool empty() const noexcept { return size() == 0; }
    /// @throws villanelle::index_out_of_range when index is not below size()
    T at(std::size_t index) const {
        if (index >= size()) {
            ::villanelle::detail::raise_index_out_of_range(index, size());
        }
        return (*items_)[index];
    }
    /// @throws villanelle::index_out_of_range when empty
    T front() const { return at(0); }
    /// @throws villanelle::index_out_of_range when empty
    T back() const { return at(empty() ? 0 : size() - 1); }

    /// Element by element.
    friend bool operator==(const sequence& a, const sequence& b) {
        if (a.size() != b.size()) {
            return false;
        }
        for (std::size_t i = 0; i < a.size(); ++i) {
            if (!((*a.items_)[i] == (*b.items_)[i])) {
                return false;
            }
        }
        return true;
    }

private:
    storage items_;  // null for an empty sequence: making one allocates nothing
};

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_SUPPORT_SEQUENCE_HPP
