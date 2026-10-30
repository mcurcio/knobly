// villanelle::ordered_map<K, V>: the binding's one map type (design.md 1.3; frozen-m2.md 3.1). Every member is
// defined here, so compiled mode's explicit instantiations (implementation.hpp) cover it for every element type.
#ifndef VILLANELLE_SUPPORT_ORDERED_MAP_HPP
#define VILLANELLE_SUPPORT_ORDERED_MAP_HPP

#include <cstddef>
#include <initializer_list>
#include <iterator>
#include <memory>
#include <optional>
#include <utility>
#include <vector>

#include <villanelle/detail/raise.hpp>
#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN

/// Insertion-ordered, lookup by key (its ==, so a handle key compares by identity), shared until changed (copy on
/// write): copying one is one pointer, and an iterator keeps the storage it walks, so a later change never
/// invalidates it.
template <class Key, class Value>
class ordered_map {
    using storage = std::vector<std::pair<Key, Value>>;

public:
    using value_type = std::pair<Key, Value>;

    /// Insertion order; *it is a value_type (a prvalue).
    class iterator {
    public:
        using value_type = std::pair<Key, Value>;
        using difference_type = std::ptrdiff_t;
        using iterator_concept = std::forward_iterator_tag;
        using iterator_category = std::input_iterator_tag;  // *it is no reference

        iterator() = default;
        value_type operator*() const { return (*items_)[at_]; }
        iterator& operator++() noexcept {
            ++at_;
            return *this;
        }
        iterator operator++(int) noexcept {
            iterator before = *this;
            ++at_;
            return before;
        }
        friend bool operator==(const iterator& a, const iterator& b) noexcept { return a.at_ == b.at_; }

    private:
        friend class ordered_map;
        iterator(std::shared_ptr<const storage> items, std::size_t at) noexcept : items_(std::move(items)), at_(at) {}
        std::shared_ptr<const storage> items_;
        std::size_t at_ = 0;
    };

    ordered_map() = default;
    /// A repeated key keeps its first place and its last value.
    ordered_map(std::initializer_list<value_type> items) {
        for (const value_type& item : items) {
            insert_or_assign(item.first, item.second);
        }
    }

    iterator begin() const noexcept { return iterator(items_, 0); }
    iterator end() const noexcept { return iterator(items_, size()); }
    std::size_t size() const noexcept { return items_ ? items_->size() : 0; }
    bool empty() const noexcept { return size() == 0; }
    bool contains(const Key& key) const { return position(key) != npos; }
    /// @throws villanelle::index_out_of_range when the key is absent
    Value at(const Key& key) const {
        const std::size_t at = position(key);
        if (at == npos) {
            ::villanelle::detail::raise_missing_key();
        }
        return (*items_)[at].second;
    }
    /// The value, or nullopt when the key is absent.
    std::optional<Value> find(const Key& key) const {
        const std::size_t at = position(key);
        if (at == npos) {
            return std::nullopt;
        }
        return (*items_)[at].second;
    }
    /// A key already there keeps its place and takes the new value; a new one goes at the end.
    void insert_or_assign(Key key, Value value) {
        storage& items = own();
        for (value_type& item : items) {
            if (item.first == key) {
                item.second = std::move(value);
                return;
            }
        }
        items.emplace_back(std::move(key), std::move(value));
    }
    /// Whether the key was there.
    bool erase(const Key& key) {
        const std::size_t at = position(key);
        if (at == npos) {
            return false;
        }
        storage& items = own();
        items.erase(items.begin() + static_cast<std::ptrdiff_t>(at));
        return true;
    }
    /// The same pairs in the same order.
    friend bool operator==(const ordered_map& a, const ordered_map& b) {
        if (a.size() != b.size()) {
            return false;
        }
        for (std::size_t i = 0; i < a.size(); ++i) {
            if (!((*a.items_)[i].first == (*b.items_)[i].first) || !((*a.items_)[i].second == (*b.items_)[i].second)) {
                return false;
            }
        }
        return true;
    }

private:
    static constexpr std::size_t npos = static_cast<std::size_t>(-1);

    std::size_t position(const Key& key) const {
        for (std::size_t i = 0; i < size(); ++i) {
            if ((*items_)[i].first == key) {
                return i;
            }
        }
        return npos;
    }

    /// The storage, copied first when another map or an iterator shares it.
    storage& own() {
        if (!items_) {
            items_ = std::make_shared<storage>();
        } else if (items_.use_count() > 1) {
            items_ = std::make_shared<storage>(*items_);
        }
        return *items_;
    }

    std::shared_ptr<storage> items_;  // null for an empty map: making one allocates nothing
};

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_SUPPORT_ORDERED_MAP_HPP
