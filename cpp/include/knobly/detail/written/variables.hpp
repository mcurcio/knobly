// Variables and resolutions (spec 6.7; ts/src/written/statements.ts): a set line's $name, a snippet's parameters, an
// override; and what each reference and use line resolves to at each copy (the binding's records).
#ifndef KNOBLY_DETAIL_WRITTEN_VARIABLES_HPP
#define KNOBLY_DETAIL_WRITTEN_VARIABLES_HPP

#include <algorithm>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <knobly/detail/written/core.hpp>
#include <knobly/detail/written/document.hpp>
#include <knobly/detail/written/edits.hpp>
#include <knobly/detail/written/host.hpp>
#include <knobly/written.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace written {

namespace detail {

/// The live variable a handle shows, and its graph. @throws knobly::detached_error
template <class Handle>
variable_node* live_variable(const Handle& handle) {
    return live(node_of<variable_node>(handle));
}

inline graph_core* graph_of(const variable_node* v) {
    return v->kind == ::knobly::variable_kind::override ? v->graph : v->line->doc->graph;
}

inline std::string variable_name(const variable_node* v) {
    switch (v->kind) {
        case ::knobly::variable_kind::set:
            return set_variable_name(v->line);
        case ::knobly::variable_kind::parameter:
            return parameter_name(v);
        case ::knobly::variable_kind::override:
            return v->name;
    }
    return {};
}

/// The token of a set variable's $name, or a parameter's.
inline std::int64_t variable_token(const variable_node* v) {
    return v->kind == ::knobly::variable_kind::set ? first_arg_token(v->line) : v->token;
}

inline ::knobly::place variable_place(const variable_node* v) {
    const std::int64_t token = variable_token(v);
    return {v->line->doc->path, v->line->doc->parsed.span_of(token, token + 1)};
}

}  // namespace detail

KNOBLY_API ::knobly::variable_kind variable::kind() const noexcept {
    return detail::node_of<detail::variable_node>(*this)->kind;
}

KNOBLY_API std::string variable::name() const { return detail::variable_name(detail::live_variable(*this)); }

/// Every reference whose declaration is this variable, documents in order; none for an override.
KNOBLY_API ::knobly::sequence<::knobly::written::reference> variable::references() const {
    detail::variable_node* v = detail::live_variable(*this);
    if (v->kind == ::knobly::variable_kind::override) {
        return {};
    }
    std::vector<detail::value_node*> all;
    for (const detail::document_node* doc : detail::graph_of(v)->documents) {
        detail::references_of(doc, all);
    }
    std::vector<detail::value_node*> mine;
    for (detail::value_node* reference : all) {
        if (detail::declaration_of(reference) == v) {
            mine.push_back(reference);
        }
    }
    return detail::handles_of<::knobly::written::reference>(mine);
}

KNOBLY_API ::knobly::sequence<::knobly::written::reference_resolution> variable::wins() const {
    detail::variable_node* v = detail::live_variable(*this);
    std::vector<detail::resolution_node*> out;
    for (detail::resolution_node* r : detail::binding_of(detail::graph_of(v))->resolutions) {
        if (r->winner == v) {
            out.push_back(r);
        }
    }
    return detail::handles_of<::knobly::written::reference_resolution>(out);
}

KNOBLY_API ::knobly::sequence<::knobly::written::reference_resolution> variable::shadowed_at() const {
    detail::variable_node* v = detail::live_variable(*this);
    std::vector<detail::resolution_node*> out;
    for (detail::resolution_node* r : detail::binding_of(detail::graph_of(v))->resolutions) {
        if (std::find(r->shadowed.begin(), r->shadowed.end(), v) != r->shadowed.end()) {
            out.push_back(r);
        }
    }
    return detail::handles_of<::knobly::written::reference_resolution>(out);
}

KNOBLY_API ::knobly::place set_variable::place() const { return detail::variable_place(detail::live_variable(*this)); }

KNOBLY_API ::knobly::written::set_line set_variable::line() const {
    return detail::make_handle<::knobly::written::set_line>(detail::live_variable(*this)->line);
}

/// Its $name token only; the line keeps its handle.
KNOBLY_API void set_variable::rename(std::string_view name) const {
    detail::variable_node* v = detail::live_variable(*this);
    detail::rename_variable(v->line->doc, detail::variable_token(v), name, v->line);
}

KNOBLY_API void set_variable::set(::knobly::config_text text) const { line().set(std::move(text)); }

KNOBLY_API ::knobly::place parameter::place() const { return detail::variable_place(detail::live_variable(*this)); }

KNOBLY_API ::knobly::written::snippet_line parameter::line() const {
    return detail::make_handle<::knobly::written::snippet_line>(detail::live_variable(*this)->line);
}

/// Its $name token only; the parameter keeps its handle.
KNOBLY_API void parameter::rename(std::string_view name) const {
    detail::variable_node* v = detail::live_variable(*this);
    detail::rename_variable(v->line->doc, v->token, name, v);
}

KNOBLY_API ::knobly::written::reference reference_resolution::reference() const {
    return detail::make_handle<::knobly::written::reference>(
        detail::node_of<detail::resolution_node>(*this)->reference);
}

KNOBLY_API ::knobly::sequence<::knobly::written::written_value> reference_resolution::values() const {
    return detail::handles_of<::knobly::written::written_value>(
        detail::node_of<detail::resolution_node>(*this)->values);
}

namespace detail {

KNOBLY_API ::knobly::written::copy resolution_copy(const ::knobly::detail::view& v) {
    return make_handle<::knobly::written::copy>(static_cast<resolution_node*>(v.get())->copy);
}

KNOBLY_API std::optional<::knobly::detail::view> resolution_winner(const ::knobly::detail::view& v) {
    node* winner = static_cast<resolution_node*>(v.get())->winner;
    if (winner == nullptr) {
        return std::nullopt;
    }
    return ::knobly::detail::view(winner);
}

KNOBLY_API std::vector<::knobly::detail::view> resolution_shadowed(const ::knobly::detail::view& v) {
    std::vector<::knobly::detail::view> out;
    for (node* each : static_cast<resolution_node*>(v.get())->shadowed) {
        out.emplace_back(each);
    }
    return out;
}

}  // namespace detail

}  // namespace written

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_VARIABLES_HPP
