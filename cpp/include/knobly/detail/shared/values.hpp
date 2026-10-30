// The shared layer's values going in (spec 6.9): quote, text and a program code known at run time. Every text passes
// through detail/text_in.hpp's one decode (design.md 2.4, provisional rule).
#ifndef KNOBLY_DETAIL_SHARED_VALUES_HPP
#define KNOBLY_DETAIL_SHARED_VALUES_HPP

#include <cstddef>
#include <memory>
#include <string>
#include <string_view>

#include <knobly/detail/raise.hpp>
#include <knobly/detail/shared/rules.hpp>
#include <knobly/detail/text_in.hpp>
#include <knobly/knobly.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace detail {

/// Whether every byte of text decodes as UTF-8 and no code point is a surrogate (WTF-8 decodes one; UTF-8 has none).
KNOBLY_API bool is_utf8(std::string_view text) noexcept {
    for (std::size_t at = 0; at < text.size();) {
        char32_t code_point = 0;
        const std::size_t length = decode_utf8(text, at, code_point);
        if (length == 0 || (code_point >= 0xD800 && code_point <= 0xDFFF)) {
            return false;
        }
        at += length;
    }
    return true;
}

/// A text as JSON writes a string, for messages that quote what a program passed.
KNOBLY_API std::string quoted_for_message(std::string_view text) {
    std::string out = "\"";
    for (const char c : text) {
        if (c == '"' || c == '\\') {
            out += '\\';
        }
        out += c;
    }
    out += '"';
    return out;
}

}  // namespace detail

KNOBLY_API program_code::program_code(std::string_view code) {
    if (!::knobly::is_program_code(code)) {
        ::knobly::detail::raise(::knobly::misuse_error("a program's diagnostic code is <namespace>/<name>: " +
                                                       ::knobly::detail::quoted_for_message(code)));
    }
    owned_ = std::make_shared<const std::string>(code);
    view_ = *owned_;
}

KNOBLY_API ::knobly::config_text quote(std::string_view text) {
    if (!::knobly::detail::is_utf8(text)) {
        ::knobly::detail::raise(
            ::knobly::misuse_error("quote(): the text is not UTF-8, so it has no knobly string form"));
    }
    return ::knobly::config_text(::knobly::detail::rules::canonical_string(text));
}

KNOBLY_API ::knobly::config_text text(std::string_view raw) { return ::knobly::config_text(std::string(raw)); }

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_SHARED_VALUES_HPP
