// What differs between two renders, matched by address under the caller's key rule (spec 7.6;
// ts/src/rendered/diff.ts), and the change records a diff returns.
#ifndef KNOBLY_DETAIL_RENDERED_DIFF_HPP
#define KNOBLY_DETAIL_RENDERED_DIFF_HPP

#include <cstddef>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include <knobly/detail/rendered/nodes.hpp>
#include <knobly/detail/rendered/tree.hpp>
#include <knobly/rendered.hpp>

KNOBLY_NAMESPACE_BEGIN

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
    by_address(const render_core* render, const ::knobly::rendered::key_rule& key) : all(address_all(render, key)) {
        for (const addressed& each : all) {
            by_text.emplace(each.address.text(), each.directive);
            of.emplace(each.directive, &each.address);
        }
    }
    std::vector<addressed> all;
    std::unordered_map<std::string, directive_node*> by_text;
    std::unordered_map<const directive_node*, const ::knobly::rendered::address*> of;
};

inline ::knobly::rendered::change make_change(::knobly::change_kind kind, const ::knobly::rendered::address& address,
                                              directive_node* before, directive_node* after) {
    const auto handle = [](directive_node* d) -> std::optional<::knobly::rendered::directive> {
        if (d == nullptr) {
            return std::nullopt;
        }
        return ::knobly::detail::make_handle<::knobly::rendered::directive>(d);
    };
    return ::knobly::detail::make_handle<::knobly::rendered::change>(
        new change_node(kind, address, handle(before), handle(after)));
}

/// Removed and unknown in before's walk order, then added and changed in after's. A directive only on one side is
/// listed alone (its block is not walked); one on both sides has its block compared at its own addresses.
inline ::knobly::sequence<::knobly::rendered::change> diff(const render_core* before, const render_core* after,
                                                           const ::knobly::rendered::key_rule& key) {
    const by_address was(before, key);
    const by_address is(after, key);
    std::vector<::knobly::rendered::change> changes;
    // The unreadable statements of the container a before directive would stand in, in after: the container may hold
    // the line that is broken now, so whether the directive is gone is unknown.
    const auto unreadable_after = [&](const directive_node* directive) -> bool {
        if (directive->parent == nullptr) {
            return !after->unreadable.empty();
        }
        const auto found = is.by_text.find(was.of.at(directive->parent)->text());
        return found != is.by_text.end() && !found->second->unreadable.empty();
    };
    // Each walk is a loop over a stack of open blocks (the next directive of each), not a recursion: the tree may be
    // max_expanded_nesting deep (spec 2.5). `visit` says whether to walk a directive's block.
    const auto walk = [](const block_node* top, const auto& visit) {
        std::vector<std::pair<const block_node*, std::size_t>> stack{{top, 0}};
        while (!stack.empty()) {
            auto& [block, next] = stack.back();
            if (next == block->items.size()) {
                stack.pop_back();
                continue;
            }
            directive_node* const directive = block->items[next++];
            if (visit(directive) && directive->block != nullptr) {
                stack.emplace_back(directive->block, 0);
            }
        }
    };
    walk(before->block, [&](directive_node* directive) {
        const ::knobly::rendered::address& address = *was.of.at(directive);
        if (is.by_text.count(address.text()) != 0) {
            return true;
        }
        const ::knobly::change_kind kind =
            unreadable_after(directive) ? ::knobly::change_kind::unknown : ::knobly::change_kind::removed;
        changes.push_back(make_change(kind, address, directive, nullptr));
        return false;
    });
    walk(after->block, [&](directive_node* directive) {
        const ::knobly::rendered::address& address = *is.of.at(directive);
        const auto old = was.by_text.find(address.text());
        if (old == was.by_text.end()) {
            changes.push_back(make_change(::knobly::change_kind::added, address, nullptr, directive));
            return false;
        }
        if (!same_own(old->second, directive)) {
            changes.push_back(make_change(::knobly::change_kind::changed, address, old->second, directive));
        }
        return true;
    });
    return changes;
}

template <class Handle>
change_node* change_of(const Handle& handle) noexcept {
    return ::knobly::detail::node_of<change_node>(handle);
}

}  // namespace detail

KNOBLY_API ::knobly::sequence<::knobly::rendered::change> rendered::diff(
    const ::knobly::rendered::rendered& after) const {
    return diff(after, ::knobly::rendered::key_options{});
}

KNOBLY_API ::knobly::sequence<::knobly::rendered::change> rendered::diff(
    const ::knobly::rendered::rendered& after, ::knobly::rendered::key_options options) const {
    return detail::diff(detail::core_of(*this), detail::core_of(after), options.key);
}

// ---- changes

KNOBLY_API ::knobly::change_kind change::kind() const noexcept { return detail::change_of(*this)->kind; }

KNOBLY_API ::knobly::rendered::address change::address() const { return detail::change_of(*this)->address; }

KNOBLY_API ::knobly::rendered::directive added::after() const { return *detail::change_of(*this)->after; }

KNOBLY_API ::knobly::rendered::directive removed::before() const { return *detail::change_of(*this)->before; }

KNOBLY_API ::knobly::rendered::directive changed::before() const { return *detail::change_of(*this)->before; }

KNOBLY_API ::knobly::rendered::directive changed::after() const { return *detail::change_of(*this)->after; }

KNOBLY_API ::knobly::rendered::directive unknown::before() const { return *detail::change_of(*this)->before; }

}  // namespace rendered

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_RENDERED_DIFF_HPP
