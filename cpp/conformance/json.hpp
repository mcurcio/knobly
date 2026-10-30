// The adapter's own JSON codec (design.md 2.6, D20; frozen-m1.md section 6): standard JSON plus the lone-surrogate
// rule of spec/conformance.md 3 (a "\ud800" escape decodes to its WTF-8 bytes and encodes back as "\ud800"), which
// nlohmann/json and Boost.JSON refuse. Test code, never part of the library.
// SKELETON: declarations only; Slice T defines them.
#ifndef VILLANELLE_CONFORMANCE_JSON_HPP
#define VILLANELLE_CONFORMANCE_JSON_HPP

#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

namespace adapter::json {

struct value;
using array = std::vector<value>;
using object = std::vector<std::pair<std::string, value>>;  // insertion order kept

struct value {
    std::variant<std::nullptr_t, bool, std::int64_t, double, std::string, std::shared_ptr<array>, std::shared_ptr<object>>
        data;
};

value parse(std::string_view line);  // one request line; throws std::runtime_error on bad JSON
std::string dump(const value& v);    // one response line, ASCII only

}  // namespace adapter::json

#endif  // VILLANELLE_CONFORMANCE_JSON_HPP
