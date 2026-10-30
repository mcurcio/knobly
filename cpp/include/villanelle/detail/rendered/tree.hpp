// The rendered tree's members (spec 7.1 to 7.5; ts/src/rendered/tree.ts): the render, its directives and blocks, and
// addresses under a key rule. Built on the nodes of nodes.hpp; render.hpp makes them, diff.hpp compares two renders.
#ifndef VILLANELLE_DETAIL_RENDERED_TREE_HPP
#define VILLANELLE_DETAIL_RENDERED_TREE_HPP

#include <cstdint>
#include <functional>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <villanelle/detail/rendered/nodes.hpp>
#include <villanelle/rendered.hpp>

VILLANELLE_NAMESPACE_BEGIN

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
inline ::villanelle::rendered::address make_address(const std::optional<::villanelle::rendered::address>& parent,
                                                    ::villanelle::rendered::address_step step) {
    std::string item = "[";
    append_json_string(item, step.name());
    item += ',';
    if (const std::optional<std::string> key = step.key()) {
        append_json_string(item, *key);
    } else {
        item += "null";
    }
    item += ',' + std::to_string(step.occurrence()) + ']';
    std::vector<::villanelle::rendered::address_step> steps;
    std::string text;
    if (parent) {
        const ::villanelle::sequence<::villanelle::rendered::address_step> above = parent->steps();
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
    ::villanelle::rendered::address address;
};

/// Every directive's address under the key rule, in walk order (spec 7.4): the rule is called once per directive,
/// parents before children; an occurrence counts the earlier siblings with the same name and key.
inline std::vector<addressed> address_all(const render_core* render, const ::villanelle::rendered::key_rule& key) {
    std::vector<addressed> out;
    const auto name = [&](const auto& self, const block_node* block,
                          const std::optional<::villanelle::rendered::address>& parent) -> void {
        std::map<std::pair<std::string, std::optional<std::string>>, std::int64_t> occurrences;
        for (directive_node* directive : block->items) {
            std::optional<std::string> key_text;
            if (key) {
                key_text = key(::villanelle::detail::make_handle<::villanelle::rendered::directive>(directive));
            }
            const std::int64_t occurrence = occurrences[{directive->name, key_text}]++;
            ::villanelle::rendered::address address =
                make_address(parent, ::villanelle::rendered::address_step(directive->name, key_text, occurrence));
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
inline ::villanelle::diagnostic_error program_error(const ::villanelle::directive_origin& origin,
                                                    std::string_view message, const ::villanelle::program_code& code) {
    return ::villanelle::diagnostic_error(
        ::villanelle::located_diagnostic(code, std::string(message), origin.place(), origin.via()));
}

template <class Handle>
render_core* core_of(const Handle& handle) noexcept {
    return ::villanelle::detail::node_of<render_core>(handle);
}

template <class Handle>
directive_node* directive_of(const Handle& handle) noexcept {
    return ::villanelle::detail::node_of<directive_node>(handle);
}

inline ::villanelle::sequence<::villanelle::rendered::directive> directives_of(const block_node* block) {
    std::vector<::villanelle::rendered::directive> out;
    out.reserve(block->items.size());
    for (directive_node* directive : block->items) {
        out.push_back(::villanelle::detail::make_handle<::villanelle::rendered::directive>(directive));
    }
    return out;
}

}  // namespace detail

// ---- the render

VILLANELLE_API ::villanelle::rendered::rendered_block rendered::block() const {
    return ::villanelle::detail::make_handle<::villanelle::rendered::rendered_block>(detail::core_of(*this)->block);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::unreadable_expansion> rendered::unreadable() const {
    return detail::core_of(*this)->unreadable;
}

VILLANELLE_API ::villanelle::directive_origin rendered::origin() const { return detail::core_of(*this)->origin; }

VILLANELLE_API ::villanelle::sequence<::villanelle::located_diagnostic> rendered::diagnostics() const {
    return detail::core_of(*this)->diagnostics;
}

VILLANELLE_API ::villanelle::written::document_graph rendered::graph() const { return detail::core_of(*this)->graph; }

VILLANELLE_API ::villanelle::diagnostic_error rendered::error(std::string_view message,
                                                              ::villanelle::program_code code) const {
    return detail::program_error(detail::core_of(*this)->origin, message, code);
}

VILLANELLE_API ::villanelle::ordered_map<::villanelle::rendered::directive, ::villanelle::rendered::address>
rendered::addresses() const {
    return addresses(::villanelle::rendered::key_options{});
}

VILLANELLE_API ::villanelle::ordered_map<::villanelle::rendered::directive, ::villanelle::rendered::address>
rendered::addresses(::villanelle::rendered::key_options options) const {
    ::villanelle::ordered_map<::villanelle::rendered::directive, ::villanelle::rendered::address> out;
    for (detail::addressed& each : detail::address_all(detail::core_of(*this), options.key)) {
        out.insert_or_assign(::villanelle::detail::make_handle<::villanelle::rendered::directive>(each.directive),
                             std::move(each.address));
    }
    return out;
}

// ---- its directives

VILLANELLE_API std::string directive::name() const { return detail::directive_of(*this)->name; }

VILLANELLE_API ::villanelle::sequence<::villanelle::written::expanded_value> directive::values() const {
    return detail::directive_of(*this)->values;
}

VILLANELLE_API std::optional<::villanelle::rendered::rendered_block> directive::block() const {
    detail::block_node* block = detail::directive_of(*this)->block;
    if (block == nullptr) {
        return std::nullopt;
    }
    return ::villanelle::detail::make_handle<::villanelle::rendered::rendered_block>(block);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::unreadable_expansion> directive::unreadable() const {
    return detail::directive_of(*this)->unreadable;
}

VILLANELLE_API std::optional<::villanelle::rendered::directive> directive::parent() const {
    detail::directive_node* parent = detail::directive_of(*this)->parent;
    if (parent == nullptr) {
        return std::nullopt;
    }
    return ::villanelle::detail::make_handle<::villanelle::rendered::directive>(parent);
}

VILLANELLE_API ::villanelle::directive_origin directive::origin() const { return detail::directive_of(*this)->origin; }

VILLANELLE_API ::villanelle::written::written_directive directive::written() const {
    return detail::directive_of(*this)->written;
}

VILLANELLE_API std::optional<::villanelle::rendered::directive> directive::closest(
    std::function<bool(const ::villanelle::rendered::directive&)> predicate) const {
    for (std::optional<::villanelle::rendered::directive> at = *this; at; at = at->parent()) {
        if (predicate(*at)) {
            return at;
        }
    }
    return std::nullopt;
}

VILLANELLE_API ::villanelle::diagnostic_error directive::error(std::string_view message,
                                                               ::villanelle::program_code code) const {
    return detail::program_error(detail::directive_of(*this)->origin, message, code);
}

// ---- addresses

VILLANELLE_API std::string to_string(const ::villanelle::rendered::address& value) {
    std::string out;
    for (const ::villanelle::rendered::address_step& step : value.steps()) {
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

VILLANELLE_API ::villanelle::sequence<::villanelle::rendered::directive>
block_traits<::villanelle::rendered::directive>::items(const view& block) {
    return ::villanelle::rendered::detail::directives_of(
        static_cast<const ::villanelle::rendered::detail::block_node*>(block.get()));
}

VILLANELLE_API std::size_t block_traits<::villanelle::rendered::directive>::size(const view& block) {
    return static_cast<const ::villanelle::rendered::detail::block_node*>(block.get())->items.size();
}

VILLANELLE_API ::villanelle::rendered::directive block_traits<::villanelle::rendered::directive>::at(const view& block,
                                                                                                     std::size_t index) {
    return make_handle<::villanelle::rendered::directive>(
        static_cast<const ::villanelle::rendered::detail::block_node*>(block.get())->items[index]);
}

/// Every item is a directive; of `name` when it is so named.
VILLANELLE_API std::optional<block_traits<::villanelle::rendered::directive>::directive>
block_traits<::villanelle::rendered::directive>::as_directive(const ::villanelle::rendered::directive& item,
                                                              std::optional<std::string_view> name) {
    if (name && ::villanelle::rendered::detail::directive_of(item)->name != *name) {
        return std::nullopt;
    }
    return item;
}

VILLANELLE_API std::optional<view> block_traits<::villanelle::rendered::directive>::block_of(
    const ::villanelle::rendered::directive& item) {
    ::villanelle::rendered::detail::block_node* block = ::villanelle::rendered::detail::directive_of(item)->block;
    if (block == nullptr) {
        return std::nullopt;
    }
    return view(block);
}

}  // namespace detail

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_RENDERED_TREE_HPP
