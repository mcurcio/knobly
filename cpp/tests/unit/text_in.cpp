// detail::decode_utf8 (design.md 2.4): the provisional rule, well-formed UTF-8 plus WTF-8 surrogates.
#include <villanelle/detail/text_in.hpp>

#include <cstddef>
#include <string_view>

#include <catch2/catch_test_macros.hpp>

namespace {
struct decoded {
    std::size_t length;
    char32_t code_point;
};
constexpr decoded decode(std::string_view text, std::size_t at = 0) {
    char32_t code_point = 0xFFFFFFFF;
    const std::size_t length = villanelle::detail::decode_utf8(text, at, code_point);
    return {length, code_point};
}
}  // namespace

static_assert(decode("a").length == 1 && decode("a").code_point == U'a');  // usable in constant expressions

TEST_CASE("well-formed UTF-8 decodes to its code point and length", "[decode]") {
    CHECK(decode("\x7f").length == 1);
    CHECK(decode("\xc3\xa9").length == 2);
    CHECK(decode("\xc3\xa9").code_point == 0xE9);
    CHECK(decode("\xe2\x82\xac").code_point == 0x20AC);
    CHECK(decode("\xef\xbb\xbf").code_point == 0xFEFF);
    CHECK(decode("\xf0\x9f\x98\x80").length == 4);
    CHECK(decode("\xf0\x9f\x98\x80").code_point == 0x1F600);
    CHECK(decode("\xf4\x8f\xbf\xbf").code_point == 0x10FFFF);
    CHECK(decode("x\xc3\xa9", 1).code_point == 0xE9);
}

TEST_CASE("a surrogate's three-byte form decodes (WTF-8)", "[decode]") {
    CHECK(decode("\xed\xa0\x80").length == 3);
    CHECK(decode("\xed\xa0\x80").code_point == 0xD800);
    CHECK(decode("\xed\xbf\xbf").code_point == 0xDFFF);
}

TEST_CASE("any other invalid byte does not decode", "[decode]") {
    CHECK(decode("\x80").length == 0);              // a stray continuation byte
    CHECK(decode("\xc0\x80").length == 0);          // C0: always overlong
    CHECK(decode("\xc1\xbf").length == 0);          // C1: always overlong
    CHECK(decode("\xe0\x80\x80").length == 0);      // an overlong three-byte form
    CHECK(decode("\xf0\x80\x80\x80").length == 0);  // an overlong four-byte form
    CHECK(decode("\xf4\x90\x80\x80").length == 0);  // past U+10FFFF
    CHECK(decode("\xf5\x80\x80\x80").length == 0);  // F5 to FF never start a sequence
    CHECK(decode("\xff").length == 0);
    CHECK(decode("\xe2\x82").length == 0);      // truncated at the end of the text
    CHECK(decode("\xe2\x28\xa1").length == 0);  // a lead byte not followed by continuations
}
