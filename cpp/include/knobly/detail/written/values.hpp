// The written value handles (spec 6.6; ts/src/written/values.ts): words, strings, lists, slices, indexes and $name
// references, each pointing at its tokens in its document's current parse. A value's set keeps its node, which takes
// the new value's kind (spec 6.1): a view of the old variant keeps its shared members, and a member only the old
// variant has raises misuse_error (finding F4).
#ifndef KNOBLY_DETAIL_WRITTEN_VALUES_HPP
#define KNOBLY_DETAIL_WRITTEN_VALUES_HPP

#include <optional>
#include <string>

#include <knobly/detail/written/core.hpp>
#include <knobly/detail/written/document.hpp>
#include <knobly/detail/written/edits.hpp>
#include <knobly/detail/written/host.hpp>
#include <knobly/written.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace written {

namespace detail {

/// The live value a handle shows. @throws knobly::detached_error
template <class Handle>
value_node* live_value(const Handle& handle) {
    return live(node_of<value_node>(handle));
}

/// A variant's own member: live first, then the node must still be of that kind.
template <class Handle>
value_node* live_kind(const Handle& handle, ::knobly::value_kind kind, std::string_view member) {
    value_node* v = live_value(handle);
    require_kind(v, kind, member);
    return v;
}

inline std::optional<::knobly::written::written_value> optional_value(value_node* v) {
    if (v == nullptr) {
        return std::nullopt;
    }
    return make_handle<::knobly::written::written_value>(v);
}

}  // namespace detail

KNOBLY_API ::knobly::value_kind written_value::kind() const noexcept {
    return detail::node_of<detail::value_node>(*this)->kind;
}

KNOBLY_API std::string written_value::text() const {
    detail::value_node* v = detail::live_value(*this);
    return v->doc->parsed.text_of(v->ref.start, v->ref.end);
}

KNOBLY_API ::knobly::place written_value::place() const {
    detail::value_node* v = detail::live_value(*this);
    return {v->doc->path, v->doc->parsed.span_of(v->ref.start, v->ref.end)};
}

KNOBLY_API ::knobly::written::statement written_value::statement() const {
    return detail::make_handle<::knobly::written::statement>(detail::live_value(*this)->statement);
}

KNOBLY_API std::optional<::knobly::written::list> written_value::list() const {
    detail::value_node* v = detail::live_value(*this);
    if (v->list == nullptr) {
        return std::nullopt;
    }
    return detail::make_handle<::knobly::written::list>(v->list);
}

KNOBLY_API void written_value::set(::knobly::config_text text) const {
    detail::set_value(detail::live_value(*this), text.view());
}

KNOBLY_API ::knobly::sequence<::knobly::written::written_value> written_value::replace_with_text(
    ::knobly::config_text text) const {
    return detail::handles_of<::knobly::written::written_value>(
        detail::replace_value(detail::live_value(*this), text.view()));
}

KNOBLY_API void written_value::remove() const { detail::remove_value(detail::live_value(*this)); }

KNOBLY_API ::knobly::sequence<::knobly::written::written_value> list::items() const {
    return detail::handles_of<::knobly::written::written_value>(
        detail::live_kind(*this, ::knobly::value_kind::list, "items")->items);
}

/// The list holding this one, when it is an item: written_value::list() under the name a member of class list can
/// take (a shared member, so it works on a stale view too).
KNOBLY_API std::optional<::knobly::written::list> list::list_() const {
    detail::value_node* v = detail::live_value(*this);
    if (v->list == nullptr) {
        return std::nullopt;
    }
    return detail::make_handle<::knobly::written::list>(v->list);
}

KNOBLY_API ::knobly::written::written_value slice::name() const {
    return detail::make_handle<::knobly::written::written_value>(
        detail::live_kind(*this, ::knobly::value_kind::slice, "name")->name);
}

KNOBLY_API std::optional<::knobly::written::written_value> slice::start() const {
    return detail::optional_value(detail::live_kind(*this, ::knobly::value_kind::slice, "start")->start);
}

KNOBLY_API std::optional<::knobly::written::written_value> slice::end() const {
    return detail::optional_value(detail::live_kind(*this, ::knobly::value_kind::slice, "end")->end);
}

KNOBLY_API ::knobly::written::written_value index::name() const {
    return detail::make_handle<::knobly::written::written_value>(
        detail::live_kind(*this, ::knobly::value_kind::index, "name")->name);
}

KNOBLY_API ::knobly::written::written_value index::index_() const {
    return detail::make_handle<::knobly::written::written_value>(
        detail::live_kind(*this, ::knobly::value_kind::index, "index")->index);
}

/// Its name without $.
KNOBLY_API std::string reference::name() const {
    detail::value_node* v = detail::live_kind(*this, ::knobly::value_kind::reference, "name");
    return v->doc->parsed.text_of(v->ref.start, v->ref.end).substr(1);
}

KNOBLY_API std::optional<::knobly::written::variable> reference::declaration() const {
    detail::variable_node* found =
        detail::declaration_of(detail::live_kind(*this, ::knobly::value_kind::reference, "declaration"));
    if (found == nullptr) {
        return std::nullopt;
    }
    return detail::make_handle<::knobly::written::variable>(found);
}

KNOBLY_API ::knobly::sequence<::knobly::written::reference_resolution> reference::resolutions() const {
    detail::value_node* v = detail::live_kind(*this, ::knobly::value_kind::reference, "resolutions");
    detail::binding_core* binding = detail::binding_of(v->doc->graph);
    const auto found = binding->by_reference.find(v);
    if (found == binding->by_reference.end()) {
        return {};
    }
    return detail::handles_of<::knobly::written::reference_resolution>(found->second);
}

}  // namespace written

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_VALUES_HPP
