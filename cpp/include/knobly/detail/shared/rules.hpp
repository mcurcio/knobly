// The value rules of the grammar (NumberText, IntegerText, BooleanText; EscapeText is the grammar's own) and the
// canonical text of a value (spec 2.9): the one home of each rule in this binding. A port of ts/src/values.ts.
#ifndef KNOBLY_DETAIL_SHARED_RULES_HPP
#define KNOBLY_DETAIL_SHARED_RULES_HPP

#include <cerrno>
#include <charconv>
#include <clocale>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <optional>
#include <string>
#include <string_view>
#include <system_error>

#include <knobly/limits.hpp>
#include <knobly/support/config.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace detail::rules {

/// Digits: `0`, or a non-zero digit then digits; returns the index after them, or npos when none start at `at`.
inline std::size_t digits(std::string_view s, std::size_t at) noexcept {
    if (at >= s.size() || s[at] < '0' || s[at] > '9') {
        return std::string_view::npos;
    }
    if (s[at] == '0') {
        return at + 1;
    }
    while (at < s.size() && s[at] >= '0' && s[at] <= '9') {
        ++at;
    }
    return at;
}

/// The integer a word spells (IntegerText, `'-'? Digits`), or nullopt when it is not one or lies outside plus or
/// minus 2^53-1 (so every binding reads the same number). `-0` is 0 (spec/contract.md 3).
inline std::optional<std::int64_t> integer_of(std::string_view word) noexcept {
    const std::size_t from = !word.empty() && word.front() == '-' ? 1 : 0;
    if (digits(word, from) != word.size()) {
        return std::nullopt;
    }
    std::int64_t value = 0;
    const char* const first = word.data() + from;
    const char* const last = word.data() + word.size();
    if (const auto [end, error] = std::from_chars(first, last, value); error != std::errc() || end != last) {
        return std::nullopt;
    }
    if (value > ::knobly::written::max_safe_integer) {
        return std::nullopt;
    }
    return from == 1 ? -value : value;
}

/// The number a word spells (NumberText, a JSON number), rounded to the nearest double; nullopt when it is not one or
/// its value lies beyond the double range (1e400). Never negative zero: -0, -0.0 and -1e-400 read as 0.
inline std::optional<double> number_of(std::string_view word) {
    std::size_t at = digits(word, !word.empty() && word.front() == '-' ? 1 : 0);
    if (at == std::string_view::npos) {
        return std::nullopt;
    }
    std::size_t point_at = std::string_view::npos;
    const auto run = [&] {
        const std::size_t from = at;
        while (at < word.size() && word[at] >= '0' && word[at] <= '9') {
            ++at;
        }
        return at > from;
    };
    if (at < word.size() && word[at] == '.') {
        point_at = at++;
        if (!run()) {
            return std::nullopt;
        }
    }
    if (at < word.size() && (word[at] == 'e' || word[at] == 'E')) {
        ++at;
        if (at < word.size() && (word[at] == '+' || word[at] == '-')) {
            ++at;
        }
        if (!run()) {
            return std::nullopt;
        }
    }
    if (at != word.size()) {
        return std::nullopt;
    }
    // strtod rounds to the nearest double and keeps subnormals; floating-point std::from_chars is not available on
    // every supported platform (macOS before 13.4). strtod reads the current C locale's decimal point, so the text's
    // '.' is handed over as that point, whatever locale the program set.
    std::string text(word);
    if (point_at != std::string_view::npos) {
        const char* point = std::localeconv()->decimal_point;
        text.replace(point_at, 1, point != nullptr && *point != '\0' ? point : ".");
    }
    errno = 0;
    char* end = nullptr;
    const double value = std::strtod(text.c_str(), &end);
    if (end != text.c_str() + text.size()) {
        return std::nullopt;
    }
    if (errno == ERANGE && std::fabs(value) == HUGE_VAL) {
        return std::nullopt;  // beyond the double range
    }
    return value == 0 ? 0.0 : value;
}

/// BooleanText: the word true or false; nullopt for any other word.
inline std::optional<bool> boolean_of(std::string_view word) noexcept {
    if (word == "true") {
        return true;
    }
    if (word == "false") {
        return false;
    }
    return std::nullopt;
}

/// The text between a STRING token's quotes. A single-quoted string is raw: its text, unchanged. A double-quoted one
/// has its escapes decoded (the grammar lets only the six through).
inline std::string decode_string(std::string_view token) {
    if (token.size() < 2) {
        return {};
    }
    const std::string_view inner = token.substr(1, token.size() - 2);
    if (token.front() == '\'') {
        return std::string(inner);
    }
    std::string out;
    out.reserve(inner.size());
    for (std::size_t i = 0; i < inner.size(); ++i) {
        if (inner[i] != '\\' || i + 1 == inner.size()) {
            out += inner[i];
            continue;
        }
        const char escaped = inner[++i];
        switch (escaped) {
            case 'n':
                out += '\n';
                break;
            case 't':
                out += '\t';
                break;
            case 'r':
                out += '\r';
                break;
            default:
                out += escaped;
                break;
        }
    }
    return out;
}

/// A decoded string's canonical text: double-quoted, with \, ", newline, tab and carriage return escaped.
inline std::string canonical_string(std::string_view value) {
    std::string out = "\"";
    for (const char c : value) {
        switch (c) {
            case '\\':
                out += "\\\\";
                break;
            case '"':
                out += "\\\"";
                break;
            case '\n':
                out += "\\n";
                break;
            case '\t':
                out += "\\t";
                break;
            case '\r':
                out += "\\r";
                break;
            default:
                out += c;
                break;
        }
    }
    out += '"';
    return out;
}

/// A slice's canonical text: name[start~end], either side empty when absent.
inline std::string canonical_slice(std::string_view name, std::optional<std::int64_t> start,
                                   std::optional<std::int64_t> end) {
    std::string out(name);
    out += '[';
    if (start) {
        out += std::to_string(*start);
    }
    out += '~';
    if (end) {
        out += std::to_string(*end);
    }
    out += ']';
    return out;
}

/// An index's canonical text: name[i].
inline std::string canonical_index(std::string_view name, std::int64_t index) {
    return std::string(name) + "[" + std::to_string(index) + "]";
}

}  // namespace detail::rules
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_SHARED_RULES_HPP
