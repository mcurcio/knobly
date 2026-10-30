// Handles as values (design.md 1.3, 2.3): a moved-from handle still shows its node, every view class hashes as it
// compares (identity; an expanded value by its text, spec 2.9) and keys an unordered container, and the reads a loop
// makes of a block or a diagnostics list take no snapshot per call, so ordinary loops are linear. The program counts
// the bytes operator new hands out, to show a read allocates nothing in proportion to the block.
#include <villanelle/rendered.hpp>
#include <villanelle/villanelle.hpp>
#include <villanelle/written.hpp>

#include <atomic>
#include <cstddef>
#include <cstdlib>
#include <functional>
#include <new>
#include <string>
#include <unordered_set>
#include <utility>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

namespace {
std::atomic<std::size_t> allocated{0};
}  // namespace

// Every allocation of this program goes through these, so a test reads how many bytes a stretch of code asked for.
void* operator new(std::size_t size) {
    allocated.fetch_add(size, std::memory_order_relaxed);
    if (void* p = std::malloc(size == 0 ? 1 : size)) {
        return p;
    }
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }

namespace {

std::string many_lines(int count) {
    std::string text;
    for (int i = 0; i < count; ++i) {
        text += "a" + std::to_string(i) + " " + std::to_string(i) + ";\n";
    }
    return text;
}

/// A key that counts its comparisons, with a std::hash.
struct counted_key {
    int value;
    static inline std::size_t compares = 0;
    friend bool operator==(const counted_key& a, const counted_key& b) {
        ++compares;
        return a.value == b.value;
    }
};

}  // namespace

template <>
struct std::hash<counted_key> {
    std::size_t operator()(const counted_key& key) const noexcept { return std::hash<int>{}(key.value); }
};

static_assert(vl::detail::hashable<vw::statement>);
static_assert(vl::detail::hashable<vw::written_directive>);
static_assert(vl::detail::hashable<vw::expanded_value>);
static_assert(vl::detail::hashable<vr::directive>);
static_assert(vl::detail::hashable<vl::diagnostics>);

TEST_CASE("a moved-from handle still shows its node", "[handles]") {
    const vw::document_graph graph = fixture::load("port 80;\n");
    vw::statement s = fixture::top(graph, 0);
    const vw::statement moved = std::move(s);
    CHECK(s.kind() == vl::statement_kind::directive);  // NOLINT(bugprone-use-after-move)
    CHECK(s == moved);                                  // NOLINT(bugprone-use-after-move)
    vw::statement assigned = fixture::top(graph, 0);
    assigned = std::move(s);                            // NOLINT(bugprone-use-after-move)
    CHECK(s.as<vw::written_directive>()->name() == "port");  // NOLINT(bugprone-use-after-move)
}

TEST_CASE("view classes key unordered containers by identity", "[handles][hash]") {
    const vw::document_graph graph = fixture::load("a 1;\nb 2;\n");
    std::unordered_set<vw::statement> seen;
    for (const vw::statement& s : graph.root().block()) {
        seen.insert(s);
    }
    seen.insert(fixture::top(graph, 0));  // asked again: the same statement
    CHECK(seen.size() == 2);
    CHECK(std::hash<vw::statement>{}(fixture::top(graph, 1)) == std::hash<vw::statement>{}(fixture::top(graph, 1)));

    const vr::rendered r = vr::render(graph);
    std::unordered_set<vr::directive> directives{r.block().at(0), r.block().at(0), r.block().at(1)};
    CHECK(directives.size() == 2);
}

TEST_CASE("expanded values are equal and hash alike exactly when their texts are", "[handles][hash]") {
    const vw::document_graph graph = fixture::load("a 7 \"x\";\nb 7;\nc 8;\n");
    const vw::expansion expansion = graph.expand();
    const vw::expanded_value a7 = expansion.block().at(0).values().at(0);
    const vw::expanded_value b7 = expansion.block().at(1).values().at(0);
    const vw::expanded_value c8 = expansion.block().at(2).values().at(0);
    CHECK(a7 == b7);  // two lines, one text
    CHECK_FALSE(a7 == c8);
    CHECK(std::hash<vw::expanded_value>{}(a7) == std::hash<vw::expanded_value>{}(b7));
    std::unordered_set<vw::expanded_value> texts{a7, b7, c8, expansion.block().at(0).values().at(1)};
    CHECK(texts.size() == 3);
}

TEST_CASE("size(), at() and end() of a block take no snapshot", "[handles][block]") {
    const vw::document_graph graph = fixture::load(many_lines(2000));
    const vw::written_block block = graph.root().block();
    const vr::rendered r = vr::render(graph);
    const vr::rendered_block rendered = r.block();
    const vw::expansion_block expanded = graph.expand().block();
    std::size_t count = 0;
    const std::size_t before = allocated.load();
    for (std::size_t i = 0; i < block.size(); ++i) {
        count += block.at(i).kind() == vl::statement_kind::directive ? 1 : 0;
    }
    for (std::size_t i = 0; i < rendered.size(); ++i) {
        count += rendered.at(i) == rendered.at(i) ? 1 : 0;
    }
    for (std::size_t i = 0; i < expanded.size(); ++i) {
        count += expanded.at(i) == expanded.at(i) ? 1 : 0;
    }
    const auto end = block.end();
    CHECK(allocated.load() - before == 0);
    CHECK(count == 6000);
    // An iterator loop that calls end() each time takes one snapshot, at begin().
    const std::size_t loop_before = allocated.load();
    count = 0;
    for (auto it = block.begin(); it != block.end(); ++it) {
        ++count;
    }
    CHECK(count == 2000);
    CHECK(allocated.load() - loop_before < 2000 * 2 * sizeof(void*));  // one snapshot, not one per step
    CHECK(block.begin() + 2000 == end);
}

TEST_CASE("an iterator loop over diagnostics that adds as it goes stays in its snapshot", "[handles][diagnostics]") {
    const vl::diagnostics sink;
    const vl::located_diagnostic first(vl::diagnostic_code::unknown_snippet, "first",
                                       vl::place("main.conf", {{0, 0, 0}, {0, 0, 0}}), {});
    sink.add(first);
    std::size_t seen = 0;
    for (auto it = sink.begin(); it != sink.end(); ++it) {
        CHECK((*it).message() == "first");
        sink.add(first);  // the loop reads the snapshot taken at begin(); end() holds none
        ++seen;
    }
    CHECK(seen == 1);
    CHECK(sink.size() == 2);
}

TEST_CASE("an ordered map with a hashed key finds each key without a linear search", "[handles][ordered_map]") {
    vl::ordered_map<counted_key, int> m;
    for (int i = 0; i < 2000; ++i) {
        m.insert_or_assign(counted_key{i}, i);
    }
    counted_key::compares = 0;
    for (int i = 0; i < 2000; ++i) {
        CHECK(m.at(counted_key{i}) == i);
    }
    CHECK(counted_key::compares < 4000);  // a linear search makes about two million
    CHECK(m.erase(counted_key{0}));
    CHECK(m.at(counted_key{1999}) == 1999);
    CHECK_FALSE(m.contains(counted_key{0}));
    CHECK(m.begin() != m.end());
    CHECK((*m.begin()).first.value == 1);
}
