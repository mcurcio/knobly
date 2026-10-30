// The shared layer's people forms (spec/contract.md 2): the text each record prints as, through to_string, which
// argument-dependent lookup finds. Lines and columns count from 1, columns in bytes (the binding's unit). A port of
// ts/src/people.ts.
#ifndef KNOBLY_DETAIL_SHARED_PEOPLE_HPP
#define KNOBLY_DETAIL_SHARED_PEOPLE_HPP

#include <string>
#include <variant>

#include <knobly/knobly.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace detail {

/// A located diagnostic's code as text: E5001, or the program's own code.
KNOBLY_API std::string code_text(const std::variant<::knobly::diagnostic_code, ::knobly::program_code>& code) {
    if (const auto* own = std::get_if<::knobly::diagnostic_code>(&code)) {
        return to_string(*own);
    }
    return std::string(std::get<::knobly::program_code>(code).view());
}

}  // namespace detail

/// line:col: CODE: message, at the span's start: "1:3: E2004: unmatched bracket".
KNOBLY_API std::string to_string(const ::knobly::diagnostic& value) {
    const ::knobly::source_position start = value.span().start();
    return std::to_string(start.line() + 1) + ":" + std::to_string(start.column() + 1) + ": " +
           to_string(value.code()) + ": " + value.message();
}

/// "sink.conf:4:5": the path, then line and column from 1 at the span's start.
KNOBLY_API std::string to_string(const ::knobly::place& value) {
    const ::knobly::source_position start = value.span().start();
    return value.resolved_path() + ":" + std::to_string(start.line() + 1) + ":" + std::to_string(start.column() + 1);
}

/// "override pixels".
KNOBLY_API std::string to_string(const ::knobly::override& value) { return "override " + value.variable(); }

/// "variable pixels at main.conf:7:15".
KNOBLY_API std::string to_string(const ::knobly::step& value) {
    return std::string(to_string(value.kind())) + " " + value.name() + " at " + to_string(value.place());
}

/// "main.conf:7:15: E5001: unknown variable: $pixels".
KNOBLY_API std::string to_string(const ::knobly::located_diagnostic& value) {
    return to_string(value.place()) + ": " + ::knobly::detail::code_text(value.code()) + ": " + value.message();
}

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_SHARED_PEOPLE_HPP
