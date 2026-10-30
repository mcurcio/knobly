// The one UTF-8 policy (design.md 2.4, D17; frozen-m1.md section 5): every text entry point and the generated lexer
// decode through decode_utf8, so the owner's ruling on invalid UTF-8 (open question vil-pol) lands here alone.
// Provisional rule: well-formed UTF-8, plus WTF-8 surrogates decoded to their code point; any other byte does not
// decode (the token loop makes it one BAD_CHAR).
// SKELETON: declaration only; Slice T defines it.
#ifndef VILLANELLE_DETAIL_TEXT_IN_HPP
#define VILLANELLE_DETAIL_TEXT_IN_HPP

#include <cstddef>
#include <string_view>

#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

/// The byte length of the code point at `at` (stored in `code_point`), or 0 when the bytes there do not decode.
constexpr std::size_t decode_utf8(std::string_view text, std::size_t at, char32_t& code_point) noexcept;

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_TEXT_IN_HPP
