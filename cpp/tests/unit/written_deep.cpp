// A tree 256 levels deep after expansion (spec 2.5, MAX_EXPANDED_NESTING, E5013; kno-bzv.6): load, render, addresses,
// walk and diff run on a thread with a small stack, so a walk that recursed once per level would overflow it; one
// block more is E5013 at the statement's name.
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

#include <pthread.h>

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <functional>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

namespace {

/// Sixteen snippets of sixteen blocks, each using the next inside its blocks: `leaf` stands inside 256 expanded
/// blocks, while no text nests deeper than 17.
std::string deep_snippets(const std::string& leaf) {
    std::string blocks;
    std::string closes;
    for (int i = 0; i < 16; ++i) {
        blocks += "b { ";
        closes += "} ";
    }
    std::string out;
    for (int i = 1; i <= 16; ++i) {
        const std::string inner = i < 16 ? "@use s" + std::to_string(i + 1) + ";" : leaf;
        out += "@snippet s" + std::to_string(i) + " { " + blocks + inner + " " + closes + "}\n";
    }
    return out + "@use s1;\n";
}

/// `work` on a thread whose stack is `bytes`, with any exception it throws carried back.
void on_small_stack(std::size_t bytes, const std::function<void()>& work) {
    struct job {
        const std::function<void()>* work;
        std::exception_ptr error;
    } given{&work, nullptr};
    pthread_attr_t attr;
    REQUIRE(pthread_attr_init(&attr) == 0);
    REQUIRE(pthread_attr_setstacksize(&attr, bytes) == 0);
    pthread_t thread;
    const auto run = [](void* p) -> void* {
        auto* j = static_cast<job*>(p);
        try {
            (*j->work)();
        } catch (...) {
            j->error = std::current_exception();
        }
        return nullptr;
    };
    REQUIRE(pthread_create(&thread, &attr, run, &given) == 0);
    REQUIRE(pthread_join(thread, nullptr) == 0);
    pthread_attr_destroy(&attr);
    if (given.error) {
        std::rethrow_exception(given.error);
    }
}

#if defined(__SANITIZE_ADDRESS__)
constexpr std::size_t sanitizer_factor = 4;  // AddressSanitizer's redzones grow every frame (GCC)
#elif defined(__has_feature)
#if __has_feature(address_sanitizer)
constexpr std::size_t sanitizer_factor = 4;  // as above (Clang)
#else
constexpr std::size_t sanitizer_factor = 1;
#endif
#else
constexpr std::size_t sanitizer_factor = 1;
#endif

/// The stack the deep walks get: KNOBLY_DEEP_STACK bytes when set (to measure), else 192 KiB (four times that under
/// AddressSanitizer). Measured with these walks: Apple Clang Debug needs under 96 KiB, GCC 13 -O0 under 128 KiB, GCC 13
/// with the sanitizers under 256 KiB; with the walks that recursed once per level (bind, expansion, render, addresses,
/// diff), Apple Clang Debug needed over 192 KiB.
std::size_t stack_bytes() {
    const char* given = std::getenv("KNOBLY_DEEP_STACK");
    return given != nullptr ? static_cast<std::size_t>(std::strtoull(given, nullptr, 10))
                            : std::size_t{192} * 1024 * sanitizer_factor;
}

}  // namespace

TEST_CASE("the walks over a tree 256 levels deep after expansion fit a small stack", "[written][limits]") {
    std::size_t diagnostics = 1;
    std::size_t walked = 0;
    std::vector<std::pair<vl::change_kind, std::size_t>> changes;
    on_small_stack(stack_bytes(), [&] {
        const vr::rendered before = vr::render(fixture::load(deep_snippets("leaf;")));
        const vr::rendered after = vr::render(fixture::load(deep_snippets("leaf 1;")));
        diagnostics = before.diagnostics().size();
        for (const vr::directive& d : before.block().walk()) {
            (void)d;
            ++walked;
        }
        for (const vr::change& c : before.diff(after)) {
            changes.emplace_back(c.kind(), c.address().steps().size());
        }
    });
    CHECK(diagnostics == 0);
    CHECK(walked == 257);
    CHECK(changes == std::vector<std::pair<vl::change_kind, std::size_t>>{{vl::change_kind::changed, 257}});
}

TEST_CASE("a block past 256 levels after expansion is E5013 at its statement's name", "[written][limits]") {
    const vw::document_graph graph = fixture::load(deep_snippets("leaf { }"));
    const vl::sequence<vl::located_diagnostic> found = graph.diagnostics();
    REQUIRE(found.size() == 1);
    CHECK(found.at(0).code() ==
          std::variant<vl::diagnostic_code, vl::program_code>(vl::diagnostic_code::expanded_nesting_too_deep));
    CHECK(found.at(0).place().span().start().line() == 15);
    CHECK(found.at(0).place().span().start().column() ==
          static_cast<std::int64_t>(std::string("@snippet s16 { ").size() + 4 * 16));
}
