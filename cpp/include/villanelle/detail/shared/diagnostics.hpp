// The shared layer's diagnostics collector (spec 7.7): add, report, collect, iteration.
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_SHARED_DIAGNOSTICS_HPP
#define VILLANELLE_DETAIL_SHARED_DIAGNOSTICS_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/villanelle.hpp>

VILLANELLE_NAMESPACE_BEGIN

VILLANELLE_API diagnostics::diagnostics() { ::villanelle::detail::not_built("diagnostics::diagnostics"); }

VILLANELLE_API diagnostics::diagnostics(::villanelle::sequence<::villanelle::located_diagnostic>) {
    ::villanelle::detail::not_built("diagnostics::diagnostics");
}

VILLANELLE_API void diagnostics::add(const ::villanelle::located_diagnostic&) const {
    ::villanelle::detail::not_built("diagnostics::add");
}

VILLANELLE_API std::size_t diagnostics::size() const { ::villanelle::detail::not_built("diagnostics::size"); }

VILLANELLE_API bool diagnostics::empty() const { ::villanelle::detail::not_built("diagnostics::empty"); }

VILLANELLE_API ::villanelle::sequence<::villanelle::located_diagnostic>::iterator diagnostics::begin() const {
    ::villanelle::detail::not_built("diagnostics::begin");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::located_diagnostic>::iterator diagnostics::end() const {
    ::villanelle::detail::not_built("diagnostics::end");
}

VILLANELLE_API bool operator==(const ::villanelle::diagnostics&, const ::villanelle::diagnostics&) {
    ::villanelle::detail::not_built("operator== of diagnostics");
}

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_SHARED_DIAGNOSTICS_HPP
