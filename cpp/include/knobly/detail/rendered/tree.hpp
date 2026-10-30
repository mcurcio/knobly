// The rendered tree's members (spec 7.1 to 7.5; ts/src/rendered/tree.ts): the render, its directives and blocks, and
// addresses under a key rule. Built on the nodes of nodes.hpp; render.hpp makes them, diff.hpp compares two renders.
#ifndef KNOBLY_DETAIL_RENDERED_TREE_HPP
#define KNOBLY_DETAIL_RENDERED_TREE_HPP

#include <cstdint>
#include <functional>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <knobly/detail/rendered/nodes.hpp>
#include <knobly/rendered.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace rendered {

namespace detail {

/// A text as JSON.stringify writes a string (the address text is the same bytes in every binding, spec 7.4).
inline void append_json_string(std::string& out, std::string_view text) {
    constexpr std::string_view digits = "0123456789abcdef";
    out += '"';
    for (const char c : text) {
        const auto byte = static_cast<unsigned char>(c);
        switch (c) {
            case '"':
                out += "\\\"";
                break;
            case '\\':
                out += "\\\\";
                break;
            case '\b':
                out += "\\b";
                break;
            case '\f':
                out += "\\f";
                break;
            case '\n':
                out += "\\n";
                break;
            case '\r':
                out += "\\r";
                break;
            case '\t':
                out += "\\t";
                break;
            default:
                if (byte < 0x20U) {
                    out += "\\u00";
                    out += digits[byte >> 4U];
                    out += digits[byte & 0xFU];
                } else {
                    out += c;
                }
        }
    }
    out += '"';
}

/// The address of a directive named by `step` under `parent`: the canonical text extends the parent's.
inline ::knobly::rendered::address make_address(const std::optional<::knobly::rendered::address>& parent,
                                                ::knobly::rendered::address_step step) {
    std::string item = "[";
    append_json_string(item, step.name());
    item += ',';
    if (const std::optional<std::string> key = step.key()) {
        append_json_string(item, *key);
    } else {
        item += "null";
    }
    item += ',' + std::to_string(step.occurrence()) + ']';
    std::vector<::knobly::rendered::address_step> steps;
    std::string text;
    if (parent) {
        const ::knobly::sequence<::knobly::rendered::address_step> above = parent->steps();
        steps.assign(above.begin(), above.end());
        text = parent->text();
        text.back() = ',';  // the parent's closing ']'
    } else {
        text = "[";
    }
    steps.push_back(std::move(step));
    text += item + ']';
    return {std::move(steps), std::move(text), parent};
}

/// One directive of a render with its address.
struct addressed {
    directive_node* directive;
    ::knobly::rendered::address address;
};

/// Every directive's address under the key rule, in walk order (spec 7.4): the rule is called once per directive,
/// parents before children; an occurrence counts the earlier siblings with the same name and key.
inline std::vector<addressed> address_all(const render_core* render, const ::knobly::rendered::key_rule& key) {
    std::vector<addressed> out;
    const auto name = [&](const auto& self, const block_node* block,
                          const std::optional<::knobly::rendered::address>& parent) -> void {
        std::map<std::pair<std::string, std::optional<std::string>>, std::int64_t> occurrences;
        for (directive_node* directive : block->items) {
            std::optional<std::string> key_text;
            if (key) {
                key_text = key(::knobly::detail::make_handle<::knobly::rendered::directive>(directive));
            }
            const std::int64_t occurrence = occurrences[{directive->name, key_text}]++;
            ::knobly::rendered::address address =
                make_address(parent, ::knobly::rendered::address_step(directive->name, key_text, occurrence));
            out.push_back({directive, address});
            if (directive->block != nullptr) {
                self(self, directive->block, address);
            }
        }
    };
    name(name, render->block, std::nullopt);
    return out;
}

/// A program's own located error, placed on an origin (spec 7.1): returned, not raised.
inline ::knobly::diagnostic_error program_error(const ::knobly::directive_origin& origin, std::string_view message,
                                                const ::knobly::program_code& code) {
    return ::knobly::diagnostic_error(
        ::knobly::located_diagnostic(code, std::string(message), origin.place(), origin.via()));
}

template <class Handle>
render_core* core_of(const Handle& handle) noexcept {
    return ::knobly::detail::node_of<render_core>(handle);
}

template <class Handle>
directive_node* directive_of(const Handle& handle) noexcept {
    return ::knobly::detail::node_of<directive_node>(handle);
}

inline ::knobly::sequence<::knobly::rendered::directive> directives_of(const block_node* block) {
    std::vector<::knobly::rendered::directive> out;
    out.reserve(block->items.size());
    for (directive_node* directive : block->items) {
        out.push_back(::knobly::detail::make_handle<::knobly::rendered::directive>(directive));
    }
    return out;
}

}  // namespace detail

// ---- the render

KNOBLY_API ::knobly::rendered::rendered_block rendered::block() const {
    return ::knobly::detail::make_handle<::knobly::rendered::rendered_block>(detail::core_of(*this)->block);
}

KNOBLY_API ::knobly::sequence<::knobly::written::unreadable_expansion> rendered::unreadable() const {
    return detail::core_of(*this)->unreadable;
}

KNOBLY_API ::knobly::directive_origin rendered::origin() const { return detail::core_of(*this)->origin; }

KNOBLY_API ::knobly::sequence<::knobly::located_diagnostic> rendered::diagnostics() const {
    return detail::core_of(*this)->diagnostics;
}

KNOBLY_API ::knobly::written::document_graph rendered::graph() const { return detail::core_of(*this)->graph; }

KNOBLY_API ::knobly::diagnostic_error rendered::error(std::string_view message, ::knobly::program_code code) const {
    return detail::program_error(detail::core_of(*this)->origin, message, code);
}

KNOBLY_API ::knobly::ordered_map<::knobly::rendered::directive, ::knobly::rendered::address> rendered::addresses()
    const {
    return addresses(::knobly::rendered::key_options{});
}

KNOBLY_API ::knobly::ordered_map<::knobly::rendered::directive, ::knobly::rendered::address> rendered::addresses(
    ::knobly::rendered::key_options options) const {
    ::knobly::ordered_map<::knobly::rendered::directive, ::knobly::rendered::address> out;
    for (detail::addressed& each : detail::address_all(detail::core_of(*this), options.key)) {
        out.insert_or_assign(::knobly::detail::make_handle<::knobly::rendered::directive>(each.directive),
                             std::move(each.address));
    }
    return out;
}

// ---- its directives

KNOBLY_API std::string directive::name() const { return detail::directive_of(*this)->name; }

KNOBLY_API ::knobly::sequence<::knobly::written::expanded_value> directive::values() const {
    return detail::directive_of(*this)->values;
}

KNOBLY_API std::optional<::knobly::rendered::rendered_block> directive::block() const {
    detail::block_node* block = detail::directive_of(*this)->block;
    if (block == nullptr) {
        return std::nullopt;
    }
    return ::knobly::detail::make_handle<::knobly::rendered::rendered_block>(block);
}

KNOBLY_API ::knobly::sequence<::knobly::written::unreadable_expansion> directive::unreadable() const {
    return detail::directive_of(*this)->unreadable;
}

KNOBLY_API std::optional<::knobly::rendered::directive> directive::parent() const {
    detail::directive_node* parent = detail::directive_of(*this)->parent;
    if (parent == nullptr) {
        return std::nullopt;
    }
    return ::knobly::detail::make_handle<::knobly::rendered::directive>(parent);
}

KNOBLY_API ::knobly::directive_origin directive::origin() const { return detail::directive_of(*this)->origin; }

KNOBLY_API ::knobly::written::written_directive directive::written() const {
    return detail::directive_of(*this)->written;
}

KNOBLY_API std::optional<::knobly::rendered::directive> directive::closest(
    std::function<bool(const ::knobly::rendered::directive&)> predicate) const {
    for (std::optional<::knobly::rendered::directive> at = *this; at; at = at->parent()) {
        if (predicate(*at)) {
            return at;
        }
    }
    return std::nullopt;
}

KNOBLY_API ::knobly::diagnostic_error directive::error(std::string_view message, ::knobly::program_code code) const {
    return detail::program_error(detail::directive_of(*this)->origin, message, code);
}

// ---- addresses

KNOBLY_API std::string to_string(const ::knobly::rendered::address& value) {
    std::string out;
    for (const ::knobly::rendered::address_step& step : value.steps()) {
        if (!out.empty()) {
            out += " > ";
        }
        out += step.name();
        if (const std::optional<std::string> key = step.key()) {
            out += ' ';
            detail::append_json_string(out, *key);
        }
        if (step.occurrence() != 0) {
            out += " #" + std::to_string(step.occurrence());
        }
    }
    return out;
}

}  // namespace rendered

// ---- the rendered block's hook (support/block.hpp)

namespace detail {

KNOBLY_API ::knobly::sequence<::knobly::rendered::directive> block_traits<::knobly::rendered::directive>::items(
    const view& block) {
    return ::knobly::rendered::detail::directives_of(
        static_cast<const ::knobly::rendered::detail::block_node*>(block.get()));
}

KNOBLY_API std::size_t block_traits<::knobly::rendered::directive>::size(const view& block) {
    return static_cast<const ::knobly::rendered::detail::block_node*>(block.get())->items.size();
}

KNOBLY_API ::knobly::rendered::directive block_traits<::knobly::rendered::directive>::at(const view& block,
                                                                                         std::size_t index) {
    return make_handle<::knobly::rendered::directive>(
        static_cast<const ::knobly::rendered::detail::block_node*>(block.get())->items[index]);
}

/// Every item is a directive; of `name` when it is so named.
KNOBLY_API std::optional<block_traits<::knobly::rendered::directive>::directive>
block_traits<::knobly::rendered::directive>::as_directive(const ::knobly::rendered::directive& item,
                                                          std::optional<std::string_view> name) {
    if (name && ::knobly::rendered::detail::directive_of(item)->name != *name) {
        return std::nullopt;
    }
    return item;
}

KNOBLY_API std::optional<view> block_traits<::knobly::rendered::directive>::block_of(
    const ::knobly::rendered::directive& item) {
    ::knobly::rendered::detail::block_node* block = ::knobly::rendered::detail::directive_of(item)->block;
    if (block == nullptr) {
        return std::nullopt;
    }
    return view(block);
}

}  // namespace detail

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_RENDERED_TREE_HPP
