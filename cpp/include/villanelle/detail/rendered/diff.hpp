// What differs between two renders, matched by address under the caller's key rule (spec 7.6;
// ts/src/rendered/diff.ts), and the change records a diff returns.
#ifndef VILLANELLE_DETAIL_RENDERED_DIFF_HPP
#define VILLANELLE_DETAIL_RENDERED_DIFF_HPP

#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include <villanelle/detail/rendered/nodes.hpp>
#include <villanelle/detail/rendered/tree.hpp>
#include <villanelle/rendered.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace rendered {

namespace detail {

/// A directive's own state for "changed": its values' canonical texts and whether it has a block.
inline bool same_own(const directive_node* before, const directive_node* after) {
    if ((before->block == nullptr) != (after->block == nullptr) || before->values.size() != after->values.size()) {
        return false;
    }
    for (std::size_t i = 0; i < before->values.size(); ++i) {
        if (before->values.at(i).text() != after->values.at(i).text()) {
            return false;
        }
    }
    return true;
}

/// One render's directives by address text, and each directive's address.
struct by_address {
    by_address(const render_core* render, const ::villanelle::rendered::key_rule& key) : all(address_all(render, key)) {
        for (const addressed& each : all) {
            by_text.emplace(each.address.text(), each.directive);
            of.emplace(each.directive, &each.address);
        }
    }
    std::vector<addressed> all;
    std::unordered_map<std::string, directive_node*> by_text;
    std::unordered_map<const directive_node*, const ::villanelle::rendered::address*> of;
};

inline ::villanelle::rendered::change make_change(::villanelle::change_kind kind,
                                                  const ::villanelle::rendered::address& address,
                                                  directive_node* before, directive_node* after) {
    const auto handle = [](directive_node* d) -> std::optional<::villanelle::rendered::directive> {
        if (d == nullptr) {
            return std::nullopt;
        }
        return ::villanelle::detail::make_handle<::villanelle::rendered::directive>(d);
    };
    return ::villanelle::detail::make_handle<::villanelle::rendered::change>(
        new change_node(kind, address, handle(before), handle(after)));
}

/// Removed and unknown in before's walk order, then added and changed in after's. A directive only on one side is
/// listed alone (its block is not walked); one on both sides has its block compared at its own addresses.
inline ::villanelle::sequence<::villanelle::rendered::change> diff(const render_core* before, const render_core* after,
                                                                   const ::villanelle::rendered::key_rule& key) {
    const by_address was(before, key);
    const by_address is(after, key);
    std::vector<::villanelle::rendered::change> changes;
    // The unreadable statements of the container a before directive would stand in, in after: the container may hold
    // the line that is broken now, so whether the directive is gone is unknown.
    const auto unreadable_after = [&](const directive_node* directive) -> bool {
        if (directive->parent == nullptr) {
            return !after->unreadable.empty();
        }
        const auto found = is.by_text.find(was.of.at(directive->parent)->text());
        return found != is.by_text.end() && !found->second->unreadable.empty();
    };
    const auto walk_before = [&](const auto& self, const block_node* block) -> void {
        for (directive_node* directive : block->items) {
            const ::villanelle::rendered::address& address = *was.of.at(directive);
            if (is.by_text.count(address.text()) != 0) {
                if (directive->block != nullptr) {
                    self(self, directive->block);
                }
                continue;
            }
            const ::villanelle::change_kind kind =
                unreadable_after(directive) ? ::villanelle::change_kind::unknown : ::villanelle::change_kind::removed;
            changes.push_back(make_change(kind, address, directive, nullptr));
        }
    };
    const auto walk_after = [&](const auto& self, const block_node* block) -> void {
        for (directive_node* directive : block->items) {
            const ::villanelle::rendered::address& address = *is.of.at(directive);
            const auto old = was.by_text.find(address.text());
            if (old == was.by_text.end()) {
                changes.push_back(make_change(::villanelle::change_kind::added, address, nullptr, directive));
                continue;
            }
            if (!same_own(old->second, directive)) {
                changes.push_back(make_change(::villanelle::change_kind::changed, address, old->second, directive));
            }
            if (directive->block != nullptr) {
                self(self, directive->block);
            }
        }
    };
    walk_before(walk_before, before->block);
    walk_after(walk_after, after->block);
    return changes;
}

template <class Handle>
change_node* change_of(const Handle& handle) noexcept {
    return ::villanelle::detail::node_of<change_node>(handle);
}

}  // namespace detail

VILLANELLE_API ::villanelle::sequence<::villanelle::rendered::change> rendered::diff(
    const ::villanelle::rendered::rendered& after) const {
    return diff(after, ::villanelle::rendered::key_options{});
}

VILLANELLE_API ::villanelle::sequence<::villanelle::rendered::change> rendered::diff(
    const ::villanelle::rendered::rendered& after, ::villanelle::rendered::key_options options) const {
    return detail::diff(detail::core_of(*this), detail::core_of(after), options.key);
}

// ---- changes

VILLANELLE_API ::villanelle::change_kind change::kind() const noexcept { return detail::change_of(*this)->kind; }

VILLANELLE_API ::villanelle::rendered::address change::address() const { return detail::change_of(*this)->address; }

VILLANELLE_API bool operator==(const ::villanelle::rendered::change& a, const ::villanelle::rendered::change& b) {
    return ::villanelle::detail::access::view_of(a) == ::villanelle::detail::access::view_of(b);
}

VILLANELLE_API ::villanelle::rendered::directive added::after() const { return *detail::change_of(*this)->after; }

VILLANELLE_API ::villanelle::rendered::directive removed::before() const { return *detail::change_of(*this)->before; }

VILLANELLE_API ::villanelle::rendered::directive changed::before() const { return *detail::change_of(*this)->before; }

VILLANELLE_API ::villanelle::rendered::directive changed::after() const { return *detail::change_of(*this)->after; }

VILLANELLE_API ::villanelle::rendered::directive unknown::before() const { return *detail::change_of(*this)->before; }

}  // namespace rendered

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_RENDERED_DIFF_HPP
