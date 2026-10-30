// knobly::ordered_map<K, V>: the binding's one map type (design.md 1.3; frozen-m2.md 3.1). Every member is
// defined here, so compiled mode's explicit instantiations (implementation.hpp) cover it for every element type.
#ifndef KNOBLY_SUPPORT_ORDERED_MAP_HPP
#define KNOBLY_SUPPORT_ORDERED_MAP_HPP

#include <concepts>
#include <cstddef>
#include <functional>
#include <initializer_list>
#include <iterator>
#include <memory>
#include <optional>
#include <unordered_map>
#include <utility>
#include <vector>

#include <knobly/detail/raise.hpp>
#include <knobly/support/config.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace detail {
/// A key with a std::hash. Asked only inside ordered_map's member bodies, which are instantiated where they are used,
/// after a generated header has specialized std::hash for its view classes.
template <class Key>
concept hashable = requires(const Key& key) {
    { std::hash<Key>{}(key) } -> std::convertible_to<std::size_t>;
};
}  // namespace detail

/// Insertion-ordered, lookup by key (its ==, so a handle key compares by identity), shared until changed (copy on
/// write): copying one is one pointer, and an iterator keeps the storage it walks, so a later change never
/// invalidates it. A key with a std::hash (text, every view class) is found through a hash index, so lookup and
/// insert take constant time on average; any other key is found by a linear search.
template <class Key, class Value>
class ordered_map {
    /// The pairs in insertion order, and (for a hashed key) each key's hash to its positions.
    struct storage {
        std::vector<std::pair<Key, Value>> items;
        std::unordered_multimap<std::size_t, std::size_t> index;
    };

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
        value_type operator*() const { return items_->items[at_]; }
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
    std::size_t size() const noexcept { return items_ ? items_->items.size() : 0; }
    bool empty() const noexcept { return size() == 0; }
    bool contains(const Key& key) const { return position(key) != npos; }
    /// @throws knobly::index_out_of_range when the key is absent
    Value at(const Key& key) const {
        const std::size_t at = position(key);
        if (at == npos) {
            ::knobly::detail::raise_missing_key();
        }
        return items_->items[at].second;
    }
    /// The value, or nullopt when the key is absent.
    std::optional<Value> find(const Key& key) const {
        const std::size_t at = position(key);
        if (at == npos) {
            return std::nullopt;
        }
        return items_->items[at].second;
    }
    /// A key already there keeps its place and takes the new value; a new one goes at the end.
    void insert_or_assign(Key key, Value value) {
        const std::size_t at = position(key);
        storage& table = own();
        if (at != npos) {
            table.items[at].second = std::move(value);
            return;
        }
        if constexpr (detail::hashable<Key>) {
            table.index.emplace(hash_of(key), table.items.size());
        }
        table.items.emplace_back(std::move(key), std::move(value));
    }
    /// Whether the key was there.
    bool erase(const Key& key) {
        const std::size_t at = position(key);
        if (at == npos) {
            return false;
        }
        storage& table = own();
        table.items.erase(table.items.begin() + static_cast<std::ptrdiff_t>(at));
        if constexpr (detail::hashable<Key>) {  // every later position moved down by one
            table.index.clear();
            for (std::size_t i = 0; i < table.items.size(); ++i) {
                table.index.emplace(hash_of(table.items[i].first), i);
            }
        }
        return true;
    }
    /// The same pairs in the same order.
    friend bool operator==(const ordered_map& a, const ordered_map& b) {
        if (a.size() != b.size()) {
            return false;
        }
        for (std::size_t i = 0; i < a.size(); ++i) {
            const value_type& x = a.items_->items[i];
            const value_type& y = b.items_->items[i];
            if (!(x.first == y.first) || !(x.second == y.second)) {
                return false;
            }
        }
        return true;
    }

private:
    static constexpr std::size_t npos = static_cast<std::size_t>(-1);
    static std::size_t hash_of(const Key& key) { return std::hash<Key>{}(key); }

    std::size_t position(const Key& key) const {
        if (!items_) {
            return npos;
        }
        if constexpr (detail::hashable<Key>) {
            const auto [first, last] = items_->index.equal_range(hash_of(key));
            for (auto it = first; it != last; ++it) {
                if (items_->items[it->second].first == key) {
                    return it->second;
                }
            }
        } else {
            for (std::size_t i = 0; i < items_->items.size(); ++i) {
                if (items_->items[i].first == key) {
                    return i;
                }
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

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_SUPPORT_ORDERED_MAP_HPP
