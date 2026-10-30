// villanelle::ordered_map<K, V>: the binding's one map type (design.md 1.3; frozen-m1.md section 5).
// SKELETON: declarations only; defined in slice 2 (the first layer that returns a map).
#ifndef VILLANELLE_SUPPORT_ORDERED_MAP_HPP
#define VILLANELLE_SUPPORT_ORDERED_MAP_HPP

#include <cstddef>
#include <initializer_list>
#include <memory>
#include <optional>
#include <utility>
#include <vector>

#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN

/// Insertion-ordered, lookup by key, shared until changed (copy on write).
template <class Key, class Value>
class ordered_map {
public:
    using value_type = std::pair<Key, Value>;
    class iterator;  // insertion order; *it is a value_type

    ordered_map();
    ordered_map(std::initializer_list<value_type> items);  // a repeated key keeps its first place, last value
    iterator begin() const;
    iterator end() const;
    std::size_t size() const noexcept;
    bool empty() const noexcept;
    bool contains(const Key& key) const;
    Value at(const Key& key) const;                   // index_out_of_range when absent
    std::optional<Value> find(const Key& key) const;  // nullopt when absent
    void insert_or_assign(Key key, Value value);      // copies first if shared; a changed key keeps its place
    bool erase(const Key& key);

private:
    std::shared_ptr<std::vector<value_type>> items_;
};

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_SUPPORT_ORDERED_MAP_HPP
