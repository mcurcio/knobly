// villanelle::ordered_map<K, V> (design.md 1.3; frozen-m2.md 3.1): insertion order, lookup by ==, copy on write, at()
// of a missing key raising index_out_of_range, a repeated key in the initializer list keeping its first place and its
// last value.
#include <villanelle/villanelle.hpp>

#include <iterator>
#include <string>
#include <utility>
#include <vector>

#include <catch2/catch_test_macros.hpp>

using map = villanelle::ordered_map<std::string, int>;

namespace {

std::vector<std::pair<std::string, int>> pairs(const map& m) { return {m.begin(), m.end()}; }

}  // namespace

static_assert(std::input_iterator<map::iterator>);

TEST_CASE("insertion order, and a changed key keeps its place", "[ordered_map]") {
    map m;
    CHECK(m.empty());
    m.insert_or_assign("b", 1);
    m.insert_or_assign("a", 2);
    m.insert_or_assign("b", 3);
    CHECK(m.size() == 2);
    CHECK(pairs(m) == std::vector<std::pair<std::string, int>>{{"b", 3}, {"a", 2}});
    CHECK(m.at("a") == 2);
    CHECK(m.find("b") == 3);
    CHECK_FALSE(m.find("c").has_value());
    CHECK(m.contains("a"));
    CHECK_FALSE(m.contains("c"));
    CHECK_THROWS_AS(m.at("c"), villanelle::index_out_of_range);
    CHECK(m.erase("b"));
    CHECK_FALSE(m.erase("b"));
    m.insert_or_assign("b", 4);  // removed, then added again: at the end
    CHECK(pairs(m) == std::vector<std::pair<std::string, int>>{{"a", 2}, {"b", 4}});
}

TEST_CASE("a repeated key in the initializer list keeps its first place and its last value", "[ordered_map]") {
    const map m{{"x", 1}, {"y", 2}, {"x", 3}};
    CHECK(pairs(m) == std::vector<std::pair<std::string, int>>{{"x", 3}, {"y", 2}});
}

TEST_CASE("copy on write: a copy and an iterator keep what they saw", "[ordered_map]") {
    map a{{"k", 1}};
    const map b = a;
    const map::iterator it = a.begin();
    a.insert_or_assign("k", 2);
    a.insert_or_assign("l", 3);
    CHECK(b.at("k") == 1);
    CHECK(b.size() == 1);
    CHECK((*it).second == 1);  // the iterator's storage is the one it started on
    CHECK(a.at("k") == 2);
    map c = b;
    c.erase("k");
    CHECK(b.size() == 1);
    CHECK(c.empty());
    CHECK(b == map{{"k", 1}});
    CHECK_FALSE(b == a);
}
