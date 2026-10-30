// TEMPORARY (frozen-m2.md section 2): the body of every milestone 2 stub, so each slice starts from a build that
// compiles and links. It writes what is missing and aborts (it never throws, so it fits a noexcept stub). Each slice
// replaces its stubs; slice R deletes this file once nothing includes it (acceptance: no "not_built" under cpp/).
#ifndef VILLANELLE_DETAIL_NOT_BUILT_HPP
#define VILLANELLE_DETAIL_NOT_BUILT_HPP

#include <cstdio>
#include <cstdlib>

#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

[[noreturn]] inline void not_built(const char* what) noexcept {
    std::fputs("villanelle: not built yet: ", stderr);
    std::fputs(what, stderr);
    std::fputc('\n', stderr);
    std::abort();
}

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_NOT_BUILT_HPP
