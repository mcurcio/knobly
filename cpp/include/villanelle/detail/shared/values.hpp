// The shared layer's values going in (spec 6.9): quote, text and a program code known at run time.
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_SHARED_VALUES_HPP
#define VILLANELLE_DETAIL_SHARED_VALUES_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/villanelle.hpp>

VILLANELLE_NAMESPACE_BEGIN

VILLANELLE_API program_code::program_code(std::string_view) {
    ::villanelle::detail::not_built("program_code::program_code");
}

VILLANELLE_API ::villanelle::config_text quote(std::string_view) { ::villanelle::detail::not_built("quote"); }

VILLANELLE_API ::villanelle::config_text text(std::string_view) { ::villanelle::detail::not_built("text"); }

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_SHARED_VALUES_HPP
