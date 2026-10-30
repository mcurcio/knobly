// Variables and reference resolutions (spec 6.7).
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_WRITTEN_VARIABLES_HPP
#define VILLANELLE_DETAIL_WRITTEN_VARIABLES_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

VILLANELLE_API ::villanelle::variable_kind variable::kind() const noexcept {
    ::villanelle::detail::not_built("written::variable::kind");
}

VILLANELLE_API std::string variable::name() const { ::villanelle::detail::not_built("written::variable::name"); }

VILLANELLE_API ::villanelle::sequence<::villanelle::written::reference> variable::references() const {
    ::villanelle::detail::not_built("written::variable::references");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::reference_resolution> variable::wins() const {
    ::villanelle::detail::not_built("written::variable::wins");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::reference_resolution> variable::shadowed_at() const {
    ::villanelle::detail::not_built("written::variable::shadowed_at");
}

VILLANELLE_API bool operator==(const ::villanelle::written::variable&, const ::villanelle::written::variable&) {
    ::villanelle::detail::not_built("operator== of variable");
}

VILLANELLE_API ::villanelle::place set_variable::place() const {
    ::villanelle::detail::not_built("written::set_variable::place");
}

VILLANELLE_API ::villanelle::written::set_line set_variable::line() const {
    ::villanelle::detail::not_built("written::set_variable::line");
}

VILLANELLE_API void set_variable::rename(std::string_view) const {
    ::villanelle::detail::not_built("written::set_variable::rename");
}

VILLANELLE_API void set_variable::set(::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::set_variable::set");
}

VILLANELLE_API ::villanelle::place parameter::place() const {
    ::villanelle::detail::not_built("written::parameter::place");
}

VILLANELLE_API ::villanelle::written::snippet_line parameter::line() const {
    ::villanelle::detail::not_built("written::parameter::line");
}

VILLANELLE_API void parameter::rename(std::string_view) const {
    ::villanelle::detail::not_built("written::parameter::rename");
}

VILLANELLE_API ::villanelle::written::reference reference_resolution::reference() const {
    ::villanelle::detail::not_built("written::reference_resolution::reference");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::written_value> reference_resolution::values() const {
    ::villanelle::detail::not_built("written::reference_resolution::values");
}

}  // namespace written

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_VARIABLES_HPP
