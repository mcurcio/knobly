// The expansion (spec 6.10) and the expanded value with its readers (spec 2.9; ts/src/written/{expansion,value}.ts):
// snapshots of one binding, holding live handles. A reader on a value of the wrong kind raises a located
// diagnostic_error (E4002), a problem in the config text the program learns with its place.
#ifndef KNOBLY_DETAIL_WRITTEN_EXPANSION_HPP
#define KNOBLY_DETAIL_WRITTEN_EXPANSION_HPP

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

#include <knobly/detail/raise.hpp>
#include <knobly/detail/shared/rules.hpp>
#include <knobly/detail/written/core.hpp>
#include <knobly/detail/written/document.hpp>
#include <knobly/detail/written/host.hpp>
#include <knobly/written.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace written {

namespace detail {

/// The file place and steps of an origin. An override is written in no file: it is placed on the $name that used it
/// (its first step), with the steps after that one (locate.ts).
inline std::pair<::knobly::place, ::knobly::sequence<::knobly::step>> locate(const ::knobly::origin& origin) {
    const auto place = origin.place();
    const ::knobly::sequence<::knobly::step> via = origin.via();
    if (const auto* file = std::get_if<::knobly::place>(&place)) {
        return {*file, via};
    }
    if (via.empty()) {
        ::knobly::detail::raise(::knobly::misuse_error("override " + std::get<::knobly::override>(place).variable() +
                                                       " has no variable step"));
    }
    return {via.front().place(), std::vector<::knobly::step>(via.begin() + 1, via.end())};
}

/// knobly's own located error for a value, with the code's message and a detail.
inline ::knobly::diagnostic_error code_error(const ::knobly::origin& origin, ::knobly::diagnostic_code code,
                                             std::string_view detail) {
    const auto [place, via] = locate(origin);
    return ::knobly::diagnostic_error(
        ::knobly::located_diagnostic(code, ::knobly::describe(code, detail).message, place, via));
}

/// A program's own located error (spec 7.1).
inline ::knobly::diagnostic_error program_error(const ::knobly::origin& origin, std::string_view message,
                                                const ::knobly::program_code& code) {
    const auto [place, via] = locate(origin);
    return ::knobly::diagnostic_error(::knobly::located_diagnostic(code, std::string(message), place, via));
}

template <class Handle>
const expanded_node* expanded_of(const Handle& handle) {
    return node_of<expanded_node>(handle);
}

[[noreturn]] inline void wrong_kind(const expanded_node* v, std::string_view wanted) {
    ::knobly::detail::raise(
        code_error(v->origin, ::knobly::diagnostic_code::wrong_value_kind,
                   "wanted " + std::string(wanted) + ", found a " + std::string(to_string(v->kind)) + ": " + v->text));
}

/// A variant's own member on a value of another kind (a view built by hand): a misuse.
inline const expanded_node* of_kind(const expanded_node* v, ::knobly::value_kind kind, std::string_view member) {
    if (v->kind != kind) {
        ::knobly::detail::raise(::knobly::misuse_error(std::string(member) + "(): this expanded value is a " +
                                                       std::string(to_string(v->kind))));
    }
    return v;
}

}  // namespace detail

// ---- the expansion

KNOBLY_API ::knobly::written::expansion_block expansion::block() const {
    return detail::make_handle<::knobly::written::expansion_block>(
        detail::node_of<detail::expansion_node>(*this)->block);
}

KNOBLY_API ::knobly::sequence<::knobly::written::unreadable_expansion> expansion::unreadable() const {
    return detail::handles_of<::knobly::written::unreadable_expansion>(
        detail::node_of<detail::expansion_node>(*this)->unreadable);
}

KNOBLY_API ::knobly::sequence<::knobly::located_diagnostic> expansion::diagnostics() const {
    return detail::node_of<detail::expansion_node>(*this)->diagnostics;
}

KNOBLY_API ::knobly::written::written_directive directive_expansion::written() const {
    return detail::make_handle<::knobly::written::written_directive>(
        detail::node_of<detail::directive_expansion_node>(*this)->written);
}

KNOBLY_API ::knobly::directive_origin directive_expansion::origin() const {
    return detail::node_of<detail::directive_expansion_node>(*this)->origin;
}

KNOBLY_API ::knobly::sequence<::knobly::written::expanded_value> directive_expansion::values() const {
    return detail::handles_of<::knobly::written::expanded_value>(
        detail::node_of<detail::directive_expansion_node>(*this)->values);
}

KNOBLY_API std::optional<::knobly::written::expansion_block> directive_expansion::block() const {
    detail::expansion_block_node* block = detail::node_of<detail::directive_expansion_node>(*this)->block;
    if (block == nullptr) {
        return std::nullopt;
    }
    return detail::make_handle<::knobly::written::expansion_block>(block);
}

KNOBLY_API ::knobly::sequence<::knobly::written::unreadable_expansion> directive_expansion::unreadable() const {
    return detail::handles_of<::knobly::written::unreadable_expansion>(
        detail::node_of<detail::directive_expansion_node>(*this)->unreadable);
}

KNOBLY_API ::knobly::written::statement unreadable_expansion::written() const {
    return detail::make_handle<::knobly::written::statement>(detail::node_of<detail::unreadable_node>(*this)->written);
}

KNOBLY_API ::knobly::unreadable_reason unreadable_expansion::reason() const {
    return detail::node_of<detail::unreadable_node>(*this)->reason;
}

KNOBLY_API ::knobly::directive_origin unreadable_expansion::origin() const {
    return detail::node_of<detail::unreadable_node>(*this)->origin;
}

// ---- the expanded value

KNOBLY_API ::knobly::value_kind expanded_value::kind() const noexcept { return detail::expanded_of(*this)->kind; }

KNOBLY_API std::string expanded_value::text() const { return detail::expanded_of(*this)->text; }

KNOBLY_API ::knobly::origin expanded_value::origin() const { return detail::expanded_of(*this)->origin; }

/// The $name on the statement's own line that brought it, else the written value itself.
KNOBLY_API ::knobly::written::written_value expanded_value::written() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (!v->chain.empty() && v->chain.front()->reference != nullptr) {
        return detail::make_handle<::knobly::written::written_value>(v->chain.front()->reference);
    }
    if (v->definition == nullptr) {
        ::knobly::detail::raise(::knobly::misuse_error("written(): an expanded value read on no line"));
    }
    return detail::make_handle<::knobly::written::written_value>(v->definition);
}

KNOBLY_API std::optional<::knobly::written::written_value> expanded_value::definition() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (v->definition == nullptr) {
        return std::nullopt;
    }
    return detail::make_handle<::knobly::written::written_value>(v->definition);
}

KNOBLY_API ::knobly::sequence<::knobly::written::reference_resolution> expanded_value::chain() const {
    return detail::handles_of<::knobly::written::reference_resolution>(detail::expanded_of(*this)->chain);
}

KNOBLY_API std::string expanded_value::word() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (v->kind != ::knobly::value_kind::word) {
        detail::wrong_kind(v, "a word");
    }
    return v->value;
}

KNOBLY_API std::string expanded_value::string() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (v->kind != ::knobly::value_kind::word && v->kind != ::knobly::value_kind::string) {
        detail::wrong_kind(v, "a word or a string");
    }
    return v->value;
}

KNOBLY_API double expanded_value::number() const {
    const std::optional<double> value = ::knobly::detail::rules::number_of(word());
    if (!value) {
        const detail::expanded_node* v = detail::expanded_of(*this);
        ::knobly::detail::raise(detail::code_error(v->origin, ::knobly::diagnostic_code::not_a_number, v->text));
    }
    return *value;
}

KNOBLY_API std::int64_t expanded_value::integer() const {
    const std::optional<std::int64_t> value = ::knobly::detail::rules::integer_of(word());
    if (!value) {
        const detail::expanded_node* v = detail::expanded_of(*this);
        ::knobly::detail::raise(detail::code_error(v->origin, ::knobly::diagnostic_code::not_an_integer, v->text));
    }
    return *value;
}

KNOBLY_API bool expanded_value::boolean() const {
    const std::optional<bool> value = ::knobly::detail::rules::boolean_of(word());
    if (!value) {
        const detail::expanded_node* v = detail::expanded_of(*this);
        ::knobly::detail::raise(detail::code_error(v->origin, ::knobly::diagnostic_code::not_a_boolean, v->text));
    }
    return *value;
}

KNOBLY_API ::knobly::sequence<::knobly::written::expanded_value> expanded_value::list() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (v->kind != ::knobly::value_kind::list) {
        detail::wrong_kind(v, "a list");
    }
    return detail::handles_of<::knobly::written::expanded_value>(v->items);
}

KNOBLY_API std::variant<::knobly::written::slice_value, ::knobly::written::index_value> expanded_value::slice() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (v->kind == ::knobly::value_kind::index) {
        return ::knobly::written::index_value(v->name, v->index);
    }
    if (v->kind != ::knobly::value_kind::slice) {
        detail::wrong_kind(v, "a slice or an index");
    }
    return ::knobly::written::slice_value(v->name, v->start, v->end);
}

KNOBLY_API ::knobly::diagnostic_error expanded_value::error(std::string_view message,
                                                            ::knobly::program_code code) const {
    return detail::program_error(detail::expanded_of(*this)->origin, message, code);
}

KNOBLY_API ::knobly::sequence<::knobly::written::expanded_value> expanded_list::items() const {
    return detail::handles_of<::knobly::written::expanded_value>(
        detail::of_kind(detail::expanded_of(*this), ::knobly::value_kind::list, "items")->items);
}

KNOBLY_API std::string expanded_slice::name() const {
    return detail::of_kind(detail::expanded_of(*this), ::knobly::value_kind::slice, "name")->name;
}

KNOBLY_API std::optional<std::int64_t> expanded_slice::start() const {
    return detail::of_kind(detail::expanded_of(*this), ::knobly::value_kind::slice, "start")->start;
}

KNOBLY_API std::optional<std::int64_t> expanded_slice::end() const {
    return detail::of_kind(detail::expanded_of(*this), ::knobly::value_kind::slice, "end")->end;
}

KNOBLY_API std::string expanded_index::name() const {
    return detail::of_kind(detail::expanded_of(*this), ::knobly::value_kind::index, "name")->name;
}

KNOBLY_API std::int64_t expanded_index::index() const {
    return detail::of_kind(detail::expanded_of(*this), ::knobly::value_kind::index, "index")->index;
}

}  // namespace written

namespace detail {

KNOBLY_API ::knobly::sequence<::knobly::written::directive_expansion>
block_traits<::knobly::written::directive_expansion>::items(const view& block) {
    return ::knobly::written::detail::handles_of<::knobly::written::directive_expansion>(
        static_cast<::knobly::written::detail::expansion_block_node*>(block.get())->items);
}

KNOBLY_API std::size_t block_traits<::knobly::written::directive_expansion>::size(const view& block) {
    return static_cast<::knobly::written::detail::expansion_block_node*>(block.get())->items.size();
}

KNOBLY_API ::knobly::written::directive_expansion block_traits<::knobly::written::directive_expansion>::at(
    const view& block, std::size_t index) {
    return make_handle<::knobly::written::directive_expansion>(
        static_cast<::knobly::written::detail::expansion_block_node*>(block.get())->items[index]);
}

/// Every item is a directive; of `name` when its written directive is so named.
KNOBLY_API std::optional<block_traits<::knobly::written::directive_expansion>::directive>
block_traits<::knobly::written::directive_expansion>::as_directive(const ::knobly::written::directive_expansion& item,
                                                                   std::optional<std::string_view> name) {
    if (name && item.written().name() != *name) {
        return std::nullopt;
    }
    return item;
}

KNOBLY_API std::optional<view> block_traits<::knobly::written::directive_expansion>::block_of(
    const ::knobly::written::directive_expansion& item) {
    auto* block = ::knobly::written::detail::node_of<::knobly::written::detail::directive_expansion_node>(item)->block;
    if (block == nullptr) {
        return std::nullopt;
    }
    return view(block);
}

}  // namespace detail

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_EXPANSION_HPP
