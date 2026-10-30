// extensions::include() (spec 5.1): its name, and E3005 on the @include when the line has no value. The paths that
// read values (not a string, a second value, the spec) are proven by the L3 conformance cases (frozen-m2.md 5).
#include <villanelle/extensions.hpp>

#include <memory>
#include <optional>
#include <variant>

#include <catch2/catch_test_macros.hpp>

namespace vl = villanelle;

TEST_CASE("include owns the include directive", "[include]") {
    const std::shared_ptr<vl::written::extension> include = vl::extensions::include();
    CHECK(include->directive() == "include");
}

TEST_CASE("include with no value raises E3005 placed on the @include", "[include]") {
    const vl::place at("main.conf", vl::source_span(vl::source_position(4, 1, 0), vl::source_position(12, 1, 8)));
    const vl::place used("root.conf", vl::source_span(vl::source_position(0, 0, 0), vl::source_position(4, 0, 4)));
    const vl::sequence<vl::step> via{vl::step(vl::step_kind::use, "sinks", used)};
    const vl::written::extension_use use(vl::sequence<vl::written::expanded_value>(), vl::directive_origin(at, via));

    std::optional<vl::located_diagnostic> raised;
    try {
        (void)vl::extensions::include()->specs(use);
    } catch (const vl::diagnostic_error& error) {
        raised = error.diagnostic();
    }
    REQUIRE(raised.has_value());
    CHECK(raised->code() == std::variant<vl::diagnostic_code, vl::program_code>(vl::diagnostic_code::include_bad_path));
    CHECK(raised->place() == at);
    CHECK(raised->via() == via);
    CHECK(raised->message() == vl::describe(vl::diagnostic_code::include_bad_path).message);
}
