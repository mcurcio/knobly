// The extensions definitions' entry point: <villanelle/extensions.hpp> includes it at its end in header-only mode,
// and <villanelle/implementation.hpp> in compiled mode. Every definition here carries VILLANELLE_API (or is a
// template). STUBS (frozen-m2.md): each body is not_built until slice F defines it.
#ifndef VILLANELLE_DETAIL_EXTENSIONS_DEFINITIONS_HPP
#define VILLANELLE_DETAIL_EXTENSIONS_DEFINITIONS_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/extensions.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace extensions {

VILLANELLE_API std::shared_ptr<::villanelle::written::extension> include() {
    ::villanelle::detail::not_built("extensions::include");
}

}  // namespace extensions

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_EXTENSIONS_DEFINITIONS_HPP
