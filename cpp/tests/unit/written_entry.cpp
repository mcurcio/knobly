// Entry rules and the nesting limit (spec 2.5, 2.8; cpp/include/knobly/detail/written/entry.hpp): the parser always
// runs, then its result is checked, so nesting past MAX_NESTING is the text's one diagnostic, E2010 on the bracket that
// opens level 101, while a problem the parse meets first stays the one diagnostic. Read through the edits that parse a
// given text with an entry rule, as a program meets them.
#include <knobly/written.hpp>

#include <cstddef>
#include <cstdint>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = knobly;
namespace vw = knobly::written;

namespace {

using code = std::variant<vl::diagnostic_code, vl::program_code>;

/// `count` lists, one inside the other.
std::string lists(std::size_t count) { return std::string(count, '[') + std::string(count, ']'); }

/// What `edit` refuses with: each bad text error diagnostic's code and column; empty when it is not refused.
template <class Edit>
std::vector<std::pair<code, std::int64_t>> refusal(Edit edit) {
    std::vector<std::pair<code, std::int64_t>> out;
    try {
        edit();
    } catch (const vl::bad_text_error& error) {
        for (const vl::diagnostic& d : error.diagnostics()) {
            out.emplace_back(d.code(), d.span().start().column());
        }
    }
    return out;
}

const code too_deep = vl::diagnostic_code::nesting_too_deep;
const code unexpected = vl::diagnostic_code::unexpected_token;

}  // namespace

TEST_CASE("an entry rule's text nested past the limit is one E2010 on the bracket that opens level 101",
          "[written][entry]") {
    const std::size_t limit = static_cast<std::size_t>(vl::syntax::max_nesting);
    const vw::document_graph graph = fixture::load("x 1;\n");
    const vw::written_directive x = *fixture::top(graph, 0).as<vw::written_directive>();
    using refused = std::vector<std::pair<code, std::int64_t>>;
    // valuesText (a statement's set): at the limit it is taken; one deeper is E2010, whatever follows the deep part.
    CHECK(refusal([&] { x.set(vl::text(lists(limit + 1))); }) == refused{{too_deep, 100}});
    CHECK(refusal([&] { x.set(vl::text(lists(limit + 1) + ";")); }) == refused{{too_deep, 100}});
    // A problem the parse meets before the deep part is the one diagnostic.
    CHECK(refusal([&] { x.set(vl::text("1; " + lists(limit + 1))); }) == refused{{unexpected, 1}});
    // statementsText (replace with text): the bracket's column in the given text.
    CHECK(refusal([&] { x.replace_with_text(vl::text("b " + lists(limit + 1) + ";")); }) == refused{{too_deep, 102}});
    // A statements text's first problem stays the one diagnostic, though recovery would go on to the deep statement.
    const code stray = vl::diagnostic_code::expected_closing_bracket;
    CHECK(refusal([&] { x.replace_with_text(vl::text("x; ] b " + lists(limit + 1) + ";")); }) == refused{{stray, 3}});
    CHECK(graph.root().text() == "x 1;\n");
    x.set(vl::text(lists(limit)));
    CHECK(graph.root().text() == "x " + lists(limit) + ";\n");
}
