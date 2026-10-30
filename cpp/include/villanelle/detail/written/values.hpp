// Written values and their edits (spec 6.6).
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_WRITTEN_VALUES_HPP
#define VILLANELLE_DETAIL_WRITTEN_VALUES_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

VILLANELLE_API ::villanelle::value_kind written_value::kind() const noexcept {
    ::villanelle::detail::not_built("written::written_value::kind");
}

VILLANELLE_API std::string written_value::text() const {
    ::villanelle::detail::not_built("written::written_value::text");
}

VILLANELLE_API ::villanelle::place written_value::place() const {
    ::villanelle::detail::not_built("written::written_value::place");
}

VILLANELLE_API ::villanelle::written::statement written_value::statement() const {
    ::villanelle::detail::not_built("written::written_value::statement");
}

VILLANELLE_API std::optional<::villanelle::written::list> written_value::list() const {
    ::villanelle::detail::not_built("written::written_value::list");
}

VILLANELLE_API void written_value::set(::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::written_value::set");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::written_value> written_value::replace_with_text(
    ::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::written_value::replace_with_text");
}

VILLANELLE_API void written_value::remove() const { ::villanelle::detail::not_built("written::written_value::remove"); }

VILLANELLE_API bool operator==(const ::villanelle::written::written_value&,
                               const ::villanelle::written::written_value&) {
    ::villanelle::detail::not_built("operator== of written_value");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::written_value> list::items() const {
    ::villanelle::detail::not_built("written::list::items");
}

VILLANELLE_API std::optional<::villanelle::written::list> list::list_() const {
    ::villanelle::detail::not_built("written::list::list_");
}

VILLANELLE_API ::villanelle::written::written_value slice::name() const {
    ::villanelle::detail::not_built("written::slice::name");
}

VILLANELLE_API std::optional<::villanelle::written::written_value> slice::start() const {
    ::villanelle::detail::not_built("written::slice::start");
}

VILLANELLE_API std::optional<::villanelle::written::written_value> slice::end() const {
    ::villanelle::detail::not_built("written::slice::end");
}

VILLANELLE_API ::villanelle::written::written_value index::name() const {
    ::villanelle::detail::not_built("written::index::name");
}

VILLANELLE_API ::villanelle::written::written_value index::index_() const {
    ::villanelle::detail::not_built("written::index::index_");
}

VILLANELLE_API std::string reference::name() const { ::villanelle::detail::not_built("written::reference::name"); }

VILLANELLE_API std::optional<::villanelle::written::variable> reference::declaration() const {
    ::villanelle::detail::not_built("written::reference::declaration");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::reference_resolution> reference::resolutions() const {
    ::villanelle::detail::not_built("written::reference::resolutions");
}

}  // namespace written

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_VALUES_HPP
