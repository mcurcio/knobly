// The one UTF-8 policy (design.md 2.4, D17; frozen-m1.md section 5): every text entry point and the generated lexer
// decode through decode_utf8, so the owner's ruling on invalid UTF-8 (open question vil-pol) lands here alone.
// Provisional rule: well-formed UTF-8, plus WTF-8 surrogates decoded to their code point; any other byte does not
// decode (the token loop makes it one BAD_CHAR).
#ifndef VILLANELLE_DETAIL_TEXT_IN_HPP
#define VILLANELLE_DETAIL_TEXT_IN_HPP

#include <cstddef>
#include <string_view>

#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

/// The byte length of the code point at `at` (stored in `code_point`), or 0 when the bytes there do not decode:
/// a stray continuation byte, C0, C1 or F5 to FF, a truncated sequence, an overlong form or a value past U+10FFFF.
/// A surrogate's three-byte form (ED A0 80 to ED BF BF, WTF-8) decodes. `at` is below text.size().
constexpr std::size_t decode_utf8(std::string_view text, std::size_t at, char32_t& code_point) noexcept {
    const auto byte = [&](std::size_t k) { return static_cast<unsigned char>(text[at + k]); };
    const unsigned char lead = byte(0);
    if (lead < 0x80) {
        code_point = lead;
        return 1;
    }
    const std::size_t length = lead >= 0xF0 ? 4 : lead >= 0xE0 ? 3 : lead >= 0xC2 ? 2 : 0;
    if (length == 0 || lead > 0xF4 || text.size() - at < length) {
        return 0;
    }
    char32_t value = lead & (0x7FU >> length);
    for (std::size_t k = 1; k < length; ++k) {
        if ((byte(k) & 0xC0U) != 0x80U) {
            return 0;
        }
        value = (value << 6U) | (byte(k) & 0x3FU);
    }
    if ((length == 3 && value < 0x800) || (length == 4 && (value < 0x10000 || value > 0x10FFFF))) {
        return 0;
    }
    code_point = value;
    return length;
}

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_TEXT_IN_HPP
