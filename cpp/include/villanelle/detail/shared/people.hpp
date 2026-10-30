// The shared layer's people forms (spec/contract.md 2): the text each record prints as, through to_string, which
// argument-dependent lookup finds. Lines and columns count from 1, columns in bytes (the binding's unit).
// Milestone 1 defines the syntax diagnostic's; the other forms are STUBS (frozen-m2.md) until slice W defines them.
#ifndef VILLANELLE_DETAIL_SHARED_PEOPLE_HPP
#define VILLANELLE_DETAIL_SHARED_PEOPLE_HPP

#include <string>

#include <villanelle/detail/not_built.hpp>
#include <villanelle/villanelle.hpp>

VILLANELLE_NAMESPACE_BEGIN

/// line:col: CODE: message, at the span's start: "1:3: E2004: unmatched bracket".
VILLANELLE_API std::string to_string(const ::villanelle::diagnostic& value) {
    const ::villanelle::source_position start = value.span().start();
    return std::to_string(start.line() + 1) + ":" + std::to_string(start.column() + 1) + ": " +
           to_string(value.code()) + ": " + value.message();
}

/// "sink.conf:4:5": the path, then line and column from 1 at the span's start.
VILLANELLE_API std::string to_string(const ::villanelle::place&) {
    ::villanelle::detail::not_built("to_string(place)");
}

/// "override pixels".
VILLANELLE_API std::string to_string(const ::villanelle::override&) {
    ::villanelle::detail::not_built("to_string(override)");
}

VILLANELLE_API std::string to_string(const ::villanelle::step&) { ::villanelle::detail::not_built("to_string(step)"); }

/// "main.conf:7:15: E5001: unknown variable: $pixels".
VILLANELLE_API std::string to_string(const ::villanelle::located_diagnostic&) {
    ::villanelle::detail::not_built("to_string(located_diagnostic)");
}

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_SHARED_PEOPLE_HPP
