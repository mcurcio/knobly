// extensions::include() (spec 5.1): its name, and E3005 on the @include when the line has no value. The paths that
// read values (not a string, a second value, the spec) are proven by the L3 conformance cases (frozen-m2.md 5). Also
// an extension's empty glob among several specs (spec 4.1: W3005, and resolution goes on), which no shared case has,
// and an extension that throws a warning code (spec 5: E3006).
#include <knobly/extensions.hpp>
#include <knobly/written.hpp>

#include <memory>
#include <optional>
#include <string>
#include <variant>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = knobly;
namespace vw = knobly::written;

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

namespace {

/// An extension that names fixed specs, whatever its line holds.
class fixed_specs final : public vw::extension {
public:
    explicit fixed_specs(vl::sequence<std::string> specs) : specs_(std::move(specs)) {}
    std::string directive() const override { return "both"; }
    vl::sequence<std::string> specs(const vw::extension_use&) const override { return specs_; }

private:
    vl::sequence<std::string> specs_;
};

vw::document_graph load_both(vl::sequence<std::string> specs) {
    const auto files = fixture::files({{"main.conf", "@both;\nz 1;\n"}, {"a.conf", "a 1;\n"}, {"d/x.txt", "x;\n"}});
    return vw::processor({vl::memory_source(files), {std::make_shared<fixed_specs>(std::move(specs))}})
        .load("main.conf");
}

}  // namespace

TEST_CASE("an empty glob among an extension's specs is the warning W3005, and the next spec is still spliced",
          "[include][warning]") {
    const vw::document_graph graph = load_both({"d/*.conf", "a.conf"});
    const vl::sequence<vl::located_diagnostic> found = graph.diagnostics();
    REQUIRE(found.size() == 1);
    CHECK(found.at(0).code() ==
          std::variant<vl::diagnostic_code, vl::program_code>(vl::diagnostic_code::include_matched_nothing));
    CHECK(found.at(0).severity() == vl::severity::warning);
    REQUIRE(graph.edges().size() == 1);
    CHECK(graph.edges().at(0).targets() == vl::sequence<std::string>{"a.conf"});
    const vw::expansion_block top = graph.expand().block();
    REQUIRE(top.size() == 2);
    CHECK(top.at(0).written().name() == "a");
    CHECK(top.at(1).written().name() == "z");
}

TEST_CASE("a path that matches no file after an empty glob is still E3001, after the warning", "[include][warning]") {
    const vw::document_graph graph = load_both({"d/*.conf", "missing.conf"});
    const vl::sequence<vl::located_diagnostic> found = graph.diagnostics();
    REQUIRE(found.size() == 2);
    CHECK(found.at(0).severity() == vl::severity::warning);
    CHECK(found.at(1).code() ==
          std::variant<vl::diagnostic_code, vl::program_code>(vl::diagnostic_code::include_not_found));
    CHECK(found.at(1).severity() == vl::severity::error);
    CHECK(graph.edges().at(0).targets().empty());
}

namespace {

/// An extension that throws a diagnostic error whose code is the warning W3005.
class throws_warning final : public vw::extension {
public:
    std::string directive() const override { return "warn"; }
    vl::sequence<std::string> specs(const vw::extension_use& use) const override {
        const vl::directive_origin origin = use.origin();
        throw vl::diagnostic_error(vl::located_diagnostic(vl::diagnostic_code::include_matched_nothing, "empty",
                                                          origin.place(), origin.via()));
    }
};

}  // namespace

TEST_CASE("an extension that throws a warning code gives E3006 at its name, never the warning", "[include][warning]") {
    // Owner, 2026-10-31 (kno-bzv.2): a warning is never thrown, so throwing one is the extension's mistake.
    const auto files = fixture::files({{"main.conf", "@warn x;\nz 1;\n"}});
    const vw::document_graph graph =
        vw::processor({vl::memory_source(files), {std::make_shared<throws_warning>()}}).load("main.conf");
    const vl::sequence<vl::located_diagnostic> found = graph.diagnostics();
    REQUIRE(found.size() == 1);
    CHECK(found.at(0).code() ==
          std::variant<vl::diagnostic_code, vl::program_code>(vl::diagnostic_code::extension_failed));
    CHECK(found.at(0).place().span().start() == vl::source_position(0, 0, 0));
    CHECK(found.at(0).message().find("W3005") != std::string::npos);
    const vw::expansion expanded = graph.expand();
    REQUIRE(expanded.unreadable().size() == 1);
    CHECK(expanded.unreadable().at(0).reason() == vl::unreadable_reason::extension);
    REQUIRE(expanded.block().size() == 1);
    CHECK(expanded.block().at(0).written().name() == "z");
}
