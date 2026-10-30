// The C++ binding's conformance adapter (spec/conformance.md): the shared driver runs the corpora through it over
// standard input and output, one JSON request per line and one response per line. Milestone 1 claims level 0 with
// "unit": "byte" (frozen-m1.md section 5.2). It uses the public headers only, like any program.
#include <villanelle/syntax.hpp>
#include <villanelle/villanelle.hpp>

#include <cstdint>
#include <cstdio>
#include <exception>
#include <iostream>
#include <optional>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#include "json.hpp"
#include "shapes.hpp"

namespace {

using adapter::json::array;
using adapter::json::object;
using adapter::json::value;

constexpr int level = 0;

/// Every dumped object, kept alive until the adapter exits; an object's id is "<index>".
std::vector<villanelle::diagnostic> dumped;

std::string keep(villanelle::diagnostic d) {
    dumped.push_back(std::move(d));
    return std::to_string(dumped.size() - 1);
}

value position(const villanelle::source_position& p) { return array{p.line(), p.column(), p.offset()}; }

value diagnostic(const villanelle::diagnostic& d) {
    return object{{"id", keep(d)},
                  {"code", villanelle::to_string(d.code())},
                  {"message", d.message()},
                  {"start", position(d.span().start())},
                  {"end", position(d.span().end())}};
}

value node(const villanelle::syntax::node& n) {
    array children;
    for (const villanelle::syntax::node& child : n.children()) {
        children.push_back(node(child));
    }
    return array{std::string(villanelle::to_string(n.kind())), n.start(), n.end(), std::move(children)};
}

value syntax_dump(const villanelle::syntax::syntax& s) {
    array tokens;
    for (const villanelle::syntax::token& t : s.tokens()) {
        tokens.push_back(array{std::string(villanelle::to_string(t.kind())), t.text(), position(t.span().start()),
                               position(t.span().end())});
    }
    array diagnostics;
    for (const villanelle::diagnostic& d : s.diagnostics()) {
        diagnostics.push_back(diagnostic(d));
    }
    return object{{"tokens", std::move(tokens)}, {"root", node(s.root())}, {"diagnostics", std::move(diagnostics)}};
}

const std::string& text_member(const value& request, std::string_view name) {
    const value* member = request.find(name);
    const auto* text = member != nullptr ? std::get_if<std::string>(&member->data) : nullptr;
    if (text == nullptr) {
        throw std::runtime_error("request has no text member '" + std::string(name) + "'");
    }
    return *text;
}

/// The ok result of one request, or nullopt for an op this level does not support.
std::optional<value> answer(const std::string& op, const value& request) {
    if (op == "hello") {
        return object{{"protocol", adapter::shapes::protocol}, {"binding", "cpp"}, {"unit", "byte"}, {"level", level}};
    }
    if (op == "parse") {
        return syntax_dump(villanelle::syntax::parse(text_member(request, "text")));
    }
    return std::nullopt;
}

/// The thrown response's body for an error of a spec 2.8 group, or nullopt for any other exception (a fault).
std::optional<value> thrown(const std::exception& error) {
    const std::optional<std::string_view> group = adapter::shapes::error_group_of(error);
    if (!group) {
        return std::nullopt;
    }
    object body{{"group", std::string(*group)}};
    if (const auto* e = dynamic_cast<const villanelle::diagnostic_error*>(&error)) {
        const auto code = e->diagnostic().code();
        body.emplace_back("code", std::holds_alternative<villanelle::diagnostic_code>(code)
                                      ? villanelle::to_string(std::get<villanelle::diagnostic_code>(code))
                                      : std::string(std::get<villanelle::program_code>(code).view()));
    }
    if (const auto* e = dynamic_cast<const villanelle::bad_text_error*>(&error)) {
        array diagnostics;
        for (const villanelle::diagnostic& d : e->diagnostics()) {
            diagnostics.push_back(diagnostic(d));
        }
        body.emplace_back("diagnostics", std::move(diagnostics));
    }
    const auto paths = [&](const villanelle::sequence<std::string>& list) {
        array out;
        for (const std::string& path : list) {
            out.emplace_back(path);
        }
        body.emplace_back("paths", std::move(out));
    };
    if (const auto* e = dynamic_cast<const villanelle::read_error*>(&error)) {
        paths(e->paths());
    } else if (const auto* s = dynamic_cast<const villanelle::save_error*>(&error)) {
        paths(s->paths());
    }
    return value(std::move(body));
}

value respond(const std::string& line) {
    value id;
    try {
        const value request = adapter::json::parse(line);
        if (const value* given = request.find("id")) {
            id = *given;
        }
        const std::string& op = text_member(request, "op");
        if (std::optional<value> ok = answer(op, request)) {
            return object{{"id", id}, {"ok", std::move(*ok)}};
        }
        return object{{"id", id}, {"fault", "op not supported at level " + std::to_string(level) + ": " + op}};
    } catch (const std::exception& error) {
        if (std::optional<value> body = thrown(error)) {
            return object{{"id", id}, {"thrown", std::move(*body)}};
        }
        return object{{"id", id}, {"fault", std::string(error.what())}};
    }
}

}  // namespace

int main() {
    std::ios::sync_with_stdio(false);
    std::string line;
    while (std::getline(std::cin, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        const std::string response = adapter::json::dump(respond(line)) + "\n";
        std::fwrite(response.data(), 1, response.size(), stdout);
        std::fflush(stdout);
    }
    return 0;
}
