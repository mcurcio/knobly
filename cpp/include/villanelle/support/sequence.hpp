// villanelle::sequence<T>: the binding's one list type (design.md 1.3, 2.3; frozen-m1.md section 5).
// SKELETON: declarations only; Slice T defines every member (M1 needs it whole: the syntax layer's lists).
#ifndef VILLANELLE_SUPPORT_SEQUENCE_HPP
#define VILLANELLE_SUPPORT_SEQUENCE_HPP

#include <cstddef>
#include <initializer_list>
#include <memory>
#include <vector>

#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN

/// An immutable, shared list: copying is one pointer; elements come back by value. T may be incomplete where the
/// sequence is declared (a node holds a sequence of nodes).
template <class T>
class sequence {
public:
    class iterator;  // random access; *it is a T (a prvalue)
    using value_type = T;
    using size_type = std::size_t;

    sequence();
    sequence(std::vector<T> items);  // NOLINT(google-explicit-constructor): a vector or a braced list converts
    sequence(std::initializer_list<T> items);
    iterator begin() const;
    iterator end() const;
    std::size_t size() const noexcept;
    bool empty() const noexcept;
    T at(std::size_t index) const;  // index_out_of_range
    T front() const;                // index_out_of_range when empty
    T back() const;                 // index_out_of_range when empty
    template <class U>
    friend bool operator==(const sequence<U>& a, const sequence<U>& b);  // element by element

private:
    std::shared_ptr<const std::vector<T>> items_;
};

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_SUPPORT_SEQUENCE_HPP
