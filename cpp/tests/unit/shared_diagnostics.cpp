// The diagnostics collector (spec 7.7): add, report (a program's problem placed on a locatable) and collect (a
// reader's diagnostic error recorded instead of ending the program), for a value-returning and a void read; the
// people forms it prints with.
#include <knobly/knobly.hpp>
#include <knobly/written.hpp>

#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = knobly;
namespace vw = knobly::written;

namespace {

std::vector<std::string> texts(const vl::diagnostics& sink) {
    std::vector<std::string> out;
    for (const vl::located_diagnostic& d : sink) {
        out.push_back(vl::to_string(d));
    }
    return out;
}

}  // namespace

TEST_CASE("add, report and iteration keep the order of arrival", "[diagnostics]") {
    const vw::document_graph graph = fixture::load("x 1 two;\ny $missing;\n");
    const vl::diagnostics sink(graph.diagnostics());  // starts with the load's
    CHECK(sink.size() == 1);
    CHECK(texts(sink) == std::vector<std::string>{"main.conf:2:3: E5001: unknown variable: $missing"});
    const vw::expanded_value two = graph.expand().block().at(0).values().at(1);
    sink.report(two, "two is not allowed", "app/two");
    sink.add(vl::located_diagnostic(vl::diagnostic_code::unknown_snippet, "made by hand",
                                    vl::place("other.conf", {{0, 0, 0}, {0, 0, 0}}), {}));
    CHECK(texts(sink) == std::vector<std::string>{"main.conf:2:3: E5001: unknown variable: $missing",
                                                  "main.conf:1:5: app/two: two is not allowed",
                                                  "other.conf:1:1: E5003: made by hand"});
    const vl::diagnostics same = sink;  // a handle: copies share one list
    same.add(vl::located_diagnostic(vl::program_code("app/more"), "more", vl::place("a", {{0, 0, 0}, {0, 0, 0}}), {}));
    CHECK(sink.size() == 4);
    CHECK(sink == same);
    CHECK_FALSE(sink == vl::diagnostics());
    CHECK(vl::diagnostics().empty());
}

TEST_CASE("a diagnostic's severity is its code's, and a program's code is an error", "[diagnostics]") {
    const vl::place at("a", {{0, 0, 0}, {0, 0, 0}});
    CHECK(vl::located_diagnostic(vl::diagnostic_code::include_matched_nothing, "m", at, {}).severity() ==
          vl::severity::warning);
    CHECK(vl::located_diagnostic(vl::diagnostic_code::include_not_found, "m", at, {}).severity() ==
          vl::severity::error);
    CHECK(vl::located_diagnostic(vl::program_code("app/x"), "m", at, {}).severity() == vl::severity::error);
    CHECK(vl::diagnostic_code::include_matched_nothing != vl::diagnostic_code::include_bad_path);  // W3005, E3005
}

TEST_CASE("collect records a reader's diagnostic error and returns absent", "[diagnostics]") {
    const vw::document_graph graph = fixture::load("x 8080 nope;\n");
    const vl::sequence<vw::expanded_value> values = graph.expand().block().at(0).values();
    const vl::diagnostics sink;
    const std::optional<std::int64_t> port = sink.collect([&] { return values.at(0).integer(); });
    CHECK(port == 8080);
    const std::optional<std::int64_t> bad = sink.collect([&] { return values.at(1).integer(); });
    CHECK_FALSE(bad.has_value());
    REQUIRE(sink.size() == 1);
    CHECK(texts(sink) == std::vector<std::string>{"main.conf:1:8: E4005: not an integer: nope"});
    // A void read: true when it ran through, false when its diagnostic was recorded.
    CHECK(sink.collect([&] { static_cast<void>(values.at(0).word()); }));
    CHECK_FALSE(sink.collect([&] { static_cast<void>(values.at(0).list()); }));
    CHECK(sink.size() == 2);
    // Any other error passes through.
    CHECK_THROWS_AS(sink.collect([]() -> int { throw std::runtime_error("not a reader's"); }), std::runtime_error);
    CHECK(sink.size() == 2);
}

TEST_CASE("the people forms", "[diagnostics][people]") {
    const vl::place place("sink.conf", {{10, 3, 4}, {12, 3, 6}});
    CHECK(vl::to_string(place) == "sink.conf:4:5");
    CHECK(vl::to_string(vl::override("pixels")) == "override pixels");
    CHECK(vl::to_string(vl::step(vl::step_kind::variable, "pixels", place)) == "variable pixels at sink.conf:4:5");
    CHECK(vl::to_string(vl::located_diagnostic(vl::diagnostic_code::unknown_variable, "unknown variable: $pixels",
                                               place, {})) == "sink.conf:4:5: E5001: unknown variable: $pixels");
    const vl::located_diagnostic with_steps(vl::diagnostic_code::unknown_variable, "unknown variable: $p", place,
                                            {vl::step(vl::step_kind::use, "s", place)});
    CHECK(vw::format_diagnostic(with_steps) ==
          "sink.conf:4:5: E5001: unknown variable: $p\n  via use s at sink.conf:4:5");
    const vw::document_graph graph = fixture::load("a 1;\n\tx $p;\n");
    const vl::located_diagnostic found = graph.diagnostics().at(0);
    CHECK(vw::format_diagnostic(found, graph) == "main.conf:2:4: E5001: unknown variable: $p\n\tx $p;\n\t  ^^");
}
