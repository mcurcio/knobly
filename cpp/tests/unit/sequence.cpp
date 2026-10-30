// knobly::sequence<T> (design.md 2.3): shared immutable storage, elements by value, a random-access range.
#include <knobly/knobly.hpp>

#include <algorithm>
#include <iterator>
#include <ranges>
#include <string>
#include <vector>

#include <catch2/catch_test_macros.hpp>

using knobly::sequence;

static_assert(std::ranges::random_access_range<sequence<std::string>>);
static_assert(std::ranges::sized_range<sequence<std::string>>);
static_assert(std::random_access_iterator<sequence<int>::iterator>);
static_assert(std::is_same_v<std::iter_reference_t<sequence<std::string>::iterator>, std::string>);

namespace {
struct tree {
    int value;
    sequence<tree> children;  // T incomplete where the sequence is declared
    friend bool operator==(const tree&, const tree&) = default;
};
sequence<std::string> make() { return {std::string(40, 'a'), std::string(40, 'b')}; }
}  // namespace

TEST_CASE("an empty sequence holds nothing and refuses every index", "[sequence]") {
    const sequence<int> empty;
    CHECK(empty.empty());
    CHECK(empty.size() == 0);
    CHECK(empty.begin() == empty.end());
    CHECK_THROWS_AS(empty.at(0), knobly::index_out_of_range);
    CHECK_THROWS_AS(empty.front(), knobly::index_out_of_range);
    CHECK_THROWS_AS(empty.back(), knobly::index_out_of_range);
    CHECK(empty == sequence<int>(std::vector<int>{}));
}

TEST_CASE("elements come back by value, in order", "[sequence]") {
    const sequence<int> numbers{3, 1, 4};
    CHECK(numbers.size() == 3);
    CHECK(numbers.at(0) == 3);
    CHECK(numbers.front() == 3);
    CHECK(numbers.back() == 4);
    CHECK_THROWS_AS(numbers.at(3), knobly::index_out_of_range);
    CHECK(std::vector<int>(numbers.begin(), numbers.end()) == std::vector<int>{3, 1, 4});
    auto it = numbers.begin();
    CHECK(it[2] == 4);
    CHECK(*(it + 1) == 1);
    CHECK(numbers.end() - numbers.begin() == 3);
    CHECK(std::ranges::max(numbers) == 4);
}

TEST_CASE("a copy shares the list, and equality is element by element", "[sequence]") {
    const sequence<std::string> a = make();
    const sequence<std::string> b = a;  // NOLINT(performance-unnecessary-copy-initialization)
    CHECK(a == b);
    CHECK(a == make());
    CHECK_FALSE(a == sequence<std::string>{"x"});
}

TEST_CASE("a result bound to a reference, or a range over a temporary, never dangles", "[sequence]") {
    const std::string& second = make().at(1);  // a prvalue: its lifetime is extended
    CHECK(second == std::string(40, 'b'));
    auto it = make().begin();  // the iterator shares the list
    CHECK(*it == std::string(40, 'a'));
    std::size_t count = 0;
    for (const std::string& s : make() | std::views::filter([](const std::string& t) { return !t.empty(); })) {
        count += s.size();
    }
    CHECK(count == 80);
}

TEST_CASE("a sequence can hold its own element type", "[sequence]") {
    const tree leaf{2, {}};
    const tree root{1, {leaf, leaf}};
    CHECK(root.children.size() == 2);
    CHECK(root.children.at(1) == leaf);
}
