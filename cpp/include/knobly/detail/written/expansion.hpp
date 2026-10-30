// The expansion (spec 6.10) and the expanded value with its readers (spec 2.9; ts/src/written/{expansion,value}.ts):
// snapshots of one binding, holding live handles. A reader on a value of the wrong kind raises a located
// diagnostic_error (E4002), a problem in the config text the program learns with its place.
#ifndef VILLANELLE_DETAIL_WRITTEN_EXPANSION_HPP
#define VILLANELLE_DETAIL_WRITTEN_EXPANSION_HPP

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

#include <villanelle/detail/raise.hpp>
#include <villanelle/detail/shared/rules.hpp>
#include <villanelle/detail/written/core.hpp>
#include <villanelle/detail/written/document.hpp>
#include <villanelle/detail/written/host.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

namespace detail {

/// The file place and steps of an origin. An override is written in no file: it is placed on the $name that used it
/// (its first step), with the steps after that one (locate.ts).
inline std::pair<::villanelle::place, ::villanelle::sequence<::villanelle::step>> locate(
    const ::villanelle::origin& origin) {
    const auto place = origin.place();
    const ::villanelle::sequence<::villanelle::step> via = origin.via();
    if (const auto* file = std::get_if<::villanelle::place>(&place)) {
        return {*file, via};
    }
    if (via.empty()) {
        ::villanelle::detail::raise(::villanelle::misuse_error(
            "override " + std::get<::villanelle::override>(place).variable() + " has no variable step"));
    }
    return {via.front().place(), std::vector<::villanelle::step>(via.begin() + 1, via.end())};
}

/// villanelle's own located error for a value, with the code's message and a detail.
inline ::villanelle::diagnostic_error code_error(const ::villanelle::origin& origin, ::villanelle::diagnostic_code code,
                                                 std::string_view detail) {
    const auto [place, via] = locate(origin);
    return ::villanelle::diagnostic_error(
        ::villanelle::located_diagnostic(code, ::villanelle::describe(code, detail).message, place, via));
}

/// A program's own located error (spec 7.1).
inline ::villanelle::diagnostic_error program_error(const ::villanelle::origin& origin, std::string_view message,
                                                    const ::villanelle::program_code& code) {
    const auto [place, via] = locate(origin);
    return ::villanelle::diagnostic_error(::villanelle::located_diagnostic(code, std::string(message), place, via));
}

template <class Handle>
const expanded_node* expanded_of(const Handle& handle) {
    return node_of<expanded_node>(handle);
}

[[noreturn]] inline void wrong_kind(const expanded_node* v, std::string_view wanted) {
    ::villanelle::detail::raise(
        code_error(v->origin, ::villanelle::diagnostic_code::wrong_value_kind,
                   "wanted " + std::string(wanted) + ", found a " + std::string(to_string(v->kind)) + ": " + v->text));
}

/// A variant's own member on a value of another kind (a view built by hand): a misuse.
inline const expanded_node* of_kind(const expanded_node* v, ::villanelle::value_kind kind, std::string_view member) {
    if (v->kind != kind) {
        ::villanelle::detail::raise(::villanelle::misuse_error(std::string(member) + "(): this expanded value is a " +
                                                               std::string(to_string(v->kind))));
    }
    return v;
}

}  // namespace detail

// ---- the expansion

VILLANELLE_API ::villanelle::written::expansion_block expansion::block() const {
    return detail::make_handle<::villanelle::written::expansion_block>(
        detail::node_of<detail::expansion_node>(*this)->block);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::unreadable_expansion> expansion::unreadable() const {
    return detail::handles_of<::villanelle::written::unreadable_expansion>(
        detail::node_of<detail::expansion_node>(*this)->unreadable);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::located_diagnostic> expansion::diagnostics() const {
    return detail::node_of<detail::expansion_node>(*this)->diagnostics;
}

VILLANELLE_API ::villanelle::written::written_directive directive_expansion::written() const {
    return detail::make_handle<::villanelle::written::written_directive>(
        detail::node_of<detail::directive_expansion_node>(*this)->written);
}

VILLANELLE_API ::villanelle::directive_origin directive_expansion::origin() const {
    return detail::node_of<detail::directive_expansion_node>(*this)->origin;
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::expanded_value> directive_expansion::values() const {
    return detail::handles_of<::villanelle::written::expanded_value>(
        detail::node_of<detail::directive_expansion_node>(*this)->values);
}

VILLANELLE_API std::optional<::villanelle::written::expansion_block> directive_expansion::block() const {
    detail::expansion_block_node* block = detail::node_of<detail::directive_expansion_node>(*this)->block;
    if (block == nullptr) {
        return std::nullopt;
    }
    return detail::make_handle<::villanelle::written::expansion_block>(block);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::unreadable_expansion> directive_expansion::unreadable()
    const {
    return detail::handles_of<::villanelle::written::unreadable_expansion>(
        detail::node_of<detail::directive_expansion_node>(*this)->unreadable);
}

VILLANELLE_API ::villanelle::written::statement unreadable_expansion::written() const {
    return detail::make_handle<::villanelle::written::statement>(
        detail::node_of<detail::unreadable_node>(*this)->written);
}

VILLANELLE_API ::villanelle::unreadable_reason unreadable_expansion::reason() const {
    return detail::node_of<detail::unreadable_node>(*this)->reason;
}

VILLANELLE_API ::villanelle::directive_origin unreadable_expansion::origin() const {
    return detail::node_of<detail::unreadable_node>(*this)->origin;
}

// ---- the expanded value

VILLANELLE_API ::villanelle::value_kind expanded_value::kind() const noexcept {
    return detail::expanded_of(*this)->kind;
}

VILLANELLE_API std::string expanded_value::text() const { return detail::expanded_of(*this)->text; }

VILLANELLE_API ::villanelle::origin expanded_value::origin() const { return detail::expanded_of(*this)->origin; }

/// The $name on the statement's own line that brought it, else the written value itself.
VILLANELLE_API ::villanelle::written::written_value expanded_value::written() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (!v->chain.empty() && v->chain.front()->reference != nullptr) {
        return detail::make_handle<::villanelle::written::written_value>(v->chain.front()->reference);
    }
    if (v->definition == nullptr) {
        ::villanelle::detail::raise(::villanelle::misuse_error("written(): an expanded value read on no line"));
    }
    return detail::make_handle<::villanelle::written::written_value>(v->definition);
}

VILLANELLE_API std::optional<::villanelle::written::written_value> expanded_value::definition() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (v->definition == nullptr) {
        return std::nullopt;
    }
    return detail::make_handle<::villanelle::written::written_value>(v->definition);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::reference_resolution> expanded_value::chain() const {
    return detail::handles_of<::villanelle::written::reference_resolution>(detail::expanded_of(*this)->chain);
}

VILLANELLE_API std::string expanded_value::word() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (v->kind != ::villanelle::value_kind::word) {
        detail::wrong_kind(v, "a word");
    }
    return v->value;
}

VILLANELLE_API std::string expanded_value::string() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (v->kind != ::villanelle::value_kind::word && v->kind != ::villanelle::value_kind::string) {
        detail::wrong_kind(v, "a word or a string");
    }
    return v->value;
}

VILLANELLE_API double expanded_value::number() const {
    const std::optional<double> value = ::villanelle::detail::rules::number_of(word());
    if (!value) {
        const detail::expanded_node* v = detail::expanded_of(*this);
        ::villanelle::detail::raise(
            detail::code_error(v->origin, ::villanelle::diagnostic_code::not_a_number, v->text));
    }
    return *value;
}

VILLANELLE_API std::int64_t expanded_value::integer() const {
    const std::optional<std::int64_t> value = ::villanelle::detail::rules::integer_of(word());
    if (!value) {
        const detail::expanded_node* v = detail::expanded_of(*this);
        ::villanelle::detail::raise(
            detail::code_error(v->origin, ::villanelle::diagnostic_code::not_an_integer, v->text));
    }
    return *value;
}

VILLANELLE_API bool expanded_value::boolean() const {
    const std::optional<bool> value = ::villanelle::detail::rules::boolean_of(word());
    if (!value) {
        const detail::expanded_node* v = detail::expanded_of(*this);
        ::villanelle::detail::raise(
            detail::code_error(v->origin, ::villanelle::diagnostic_code::not_a_boolean, v->text));
    }
    return *value;
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::expanded_value> expanded_value::list() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (v->kind != ::villanelle::value_kind::list) {
        detail::wrong_kind(v, "a list");
    }
    return detail::handles_of<::villanelle::written::expanded_value>(v->items);
}

VILLANELLE_API std::variant<::villanelle::written::slice_value, ::villanelle::written::index_value>
expanded_value::slice() const {
    const detail::expanded_node* v = detail::expanded_of(*this);
    if (v->kind == ::villanelle::value_kind::index) {
        return ::villanelle::written::index_value(v->name, v->index);
    }
    if (v->kind != ::villanelle::value_kind::slice) {
        detail::wrong_kind(v, "a slice or an index");
    }
    return ::villanelle::written::slice_value(v->name, v->start, v->end);
}

VILLANELLE_API ::villanelle::diagnostic_error expanded_value::error(std::string_view message,
                                                                    ::villanelle::program_code code) const {
    return detail::program_error(detail::expanded_of(*this)->origin, message, code);
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::expanded_value> expanded_list::items() const {
    return detail::handles_of<::villanelle::written::expanded_value>(
        detail::of_kind(detail::expanded_of(*this), ::villanelle::value_kind::list, "items")->items);
}

VILLANELLE_API std::string expanded_slice::name() const {
    return detail::of_kind(detail::expanded_of(*this), ::villanelle::value_kind::slice, "name")->name;
}

VILLANELLE_API std::optional<std::int64_t> expanded_slice::start() const {
    return detail::of_kind(detail::expanded_of(*this), ::villanelle::value_kind::slice, "start")->start;
}

VILLANELLE_API std::optional<std::int64_t> expanded_slice::end() const {
    return detail::of_kind(detail::expanded_of(*this), ::villanelle::value_kind::slice, "end")->end;
}

VILLANELLE_API std::string expanded_index::name() const {
    return detail::of_kind(detail::expanded_of(*this), ::villanelle::value_kind::index, "name")->name;
}

VILLANELLE_API std::int64_t expanded_index::index() const {
    return detail::of_kind(detail::expanded_of(*this), ::villanelle::value_kind::index, "index")->index;
}

}  // namespace written

namespace detail {

VILLANELLE_API ::villanelle::sequence<::villanelle::written::directive_expansion>
block_traits<::villanelle::written::directive_expansion>::items(const view& block) {
    return ::villanelle::written::detail::handles_of<::villanelle::written::directive_expansion>(
        static_cast<::villanelle::written::detail::expansion_block_node*>(block.get())->items);
}

VILLANELLE_API std::size_t block_traits<::villanelle::written::directive_expansion>::size(const view& block) {
    return static_cast<::villanelle::written::detail::expansion_block_node*>(block.get())->items.size();
}

VILLANELLE_API ::villanelle::written::directive_expansion block_traits<::villanelle::written::directive_expansion>::at(
    const view& block, std::size_t index) {
    return make_handle<::villanelle::written::directive_expansion>(
        static_cast<::villanelle::written::detail::expansion_block_node*>(block.get())->items[index]);
}

/// Every item is a directive; of `name` when its written directive is so named.
VILLANELLE_API std::optional<block_traits<::villanelle::written::directive_expansion>::directive>
block_traits<::villanelle::written::directive_expansion>::as_directive(
    const ::villanelle::written::directive_expansion& item, std::optional<std::string_view> name) {
    if (name && item.written().name() != *name) {
        return std::nullopt;
    }
    return item;
}

VILLANELLE_API std::optional<view> block_traits<::villanelle::written::directive_expansion>::block_of(
    const ::villanelle::written::directive_expansion& item) {
    auto* block =
        ::villanelle::written::detail::node_of<::villanelle::written::detail::directive_expansion_node>(item)->block;
    if (block == nullptr) {
        return std::nullopt;
    }
    return view(block);
}

}  // namespace detail

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_EXPANSION_HPP
