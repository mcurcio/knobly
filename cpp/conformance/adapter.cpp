// The C++ binding's conformance adapter (spec/conformance.md): the shared driver runs the corpora through it over
// standard input and output, one JSON request per line and one response per line. It claims level 3 with "unit":
// "byte" (frozen-m2.md section 6): parse; load, graph, edit, save and quote on the written layer; render, diff, read,
// print, format and cut on the rendered layer and the contract; and the include extension. It uses the public headers
// only, like any program: members are spelled by the generated shapes::spelling and thrown errors named by the
// generated shapes::error_group_of.
#include <knobly/extensions.hpp>
#include <knobly/knobly.hpp>
#include <knobly/rendered.hpp>
#include <knobly/syntax.hpp>
#include <knobly/written.hpp>

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

#include "json.hpp"
#include "shapes.hpp"

// The generated spelling table knows a member a class spells otherwise (the loader's Model.spellings).
static_assert(adapter::shapes::spelling("index", "index") == "index_");
static_assert(adapter::shapes::spelling("expanded_value", "list") == "list");
static_assert(adapter::shapes::spelling("set override") == "set_override");

namespace {

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

using adapter::json::array;
using adapter::json::object;
using adapter::json::value;

constexpr int level = 3;

/// Every dumped object, kept alive until the adapter exits; an object's id is "<index>".
using kept = std::variant<vl::diagnostic, vl::place, vl::override, vl::step, vl::located_diagnostic, vw::document_graph,
                          vw::document, vw::written_block, vw::statement, vw::written_value, vw::variable,
                          vw::expanded_value, vr::rendered, vr::directive>;
std::vector<kept> dumped;

template <class T>
std::string keep(T object) {
    dumped.emplace_back(std::move(object));
    return std::to_string(dumped.size() - 1);
}

kept find(const std::string& id) {
    std::size_t at = 0;
    try {
        at = std::stoul(id);
    } catch (const std::exception&) {
        throw std::runtime_error("not an id: " + id);
    }
    if (at >= dumped.size()) {
        throw std::runtime_error("no object " + id);
    }
    return dumped[at];
}

/// A copy of the handle (the list grows, so a reference into it would not last).
template <class T>
T get(const std::string& id) {
    const kept object = find(id);
    const T* found = std::get_if<T>(&object);
    if (found == nullptr) {
        throw std::runtime_error("object " + id + " is not of the kind asked");
    }
    return *found;
}

// ---- requests

const value& member_of(const value& request, std::string_view name) {
    const value* found = request.find(name);
    if (found == nullptr) {
        throw std::runtime_error("request has no member '" + std::string(name) + "'");
    }
    return *found;
}

const std::string& text_of(const value& v, std::string_view what) {
    const auto* text = std::get_if<std::string>(&v.data);
    if (text == nullptr) {
        throw std::runtime_error(std::string(what) + " is not text");
    }
    return *text;
}

const std::string& text_member(const value& request, std::string_view name) {
    return text_of(member_of(request, name), name);
}

const array& array_of(const value& v, std::string_view what) {
    const auto* items = std::get_if<std::shared_ptr<array>>(&v.data);
    if (items == nullptr) {
        throw std::runtime_error(std::string(what) + " is not an array");
    }
    return **items;
}

const object& object_of(const value& v, std::string_view what) {
    const auto* members = std::get_if<std::shared_ptr<object>>(&v.data);
    if (members == nullptr) {
        throw std::runtime_error(std::string(what) + " is not an object");
    }
    return **members;
}

// ---- dumps (spec/conformance.md 4.2)

value position(const vl::source_position& p) { return array{p.line(), p.column(), p.offset()}; }

value place(const vl::place& p) {
    return object{{"id", keep(p)},
                  {"path", p.resolved_path()},
                  {"start", position(p.span().start())},
                  {"end", position(p.span().end())}};
}

value steps(const vl::sequence<vl::step>& via) {
    array out;
    for (const vl::step& s : via) {
        out.push_back(object{{"id", keep(s)},
                             {"kind", std::string(vl::to_string(s.kind()))},
                             {"name", s.name()},
                             {"place", place(s.place())}});
    }
    return out;
}

/// An origin's place: a file place, or an override.
value origin_place(const std::variant<vl::place, vl::override>& p) {
    if (const auto* file = std::get_if<vl::place>(&p)) {
        return place(*file);
    }
    const vl::override& o = std::get<vl::override>(p);
    return object{{"id", keep(o)}, {"override", o.variable()}};
}

value origin(const vl::origin& o) { return object{{"place", origin_place(o.place())}, {"via", steps(o.via())}}; }

value origin(const vl::directive_origin& o) { return object{{"place", place(o.place())}, {"via", steps(o.via())}}; }

std::string code_text(const std::variant<vl::diagnostic_code, vl::program_code>& code) {
    if (const auto* own = std::get_if<vl::diagnostic_code>(&code)) {
        return vl::to_string(*own);
    }
    return std::string(std::get<vl::program_code>(code).view());
}

value diagnostic(const vl::diagnostic& d) {
    return object{{"id", keep(d)},
                  {"code", vl::to_string(d.code())},
                  {"message", d.message()},
                  {"start", position(d.span().start())},
                  {"end", position(d.span().end())}};
}

value located(const vl::located_diagnostic& d) {
    return object{{"id", keep(d)},
                  {"code", code_text(d.code())},
                  {"message", d.message()},
                  {"place", place(d.place())},
                  {"via", steps(d.via())}};
}

value node(const vl::syntax::node& n) {
    array children;
    for (const vl::syntax::node& child : n.children()) {
        children.push_back(node(child));
    }
    return array{std::string(vl::to_string(n.kind())), n.start(), n.end(), std::move(children)};
}

value syntax_dump(const vl::syntax::syntax& s) {
    array tokens;
    for (const vl::syntax::token& t : s.tokens()) {
        tokens.push_back(array{std::string(vl::to_string(t.kind())), t.text(), position(t.span().start()),
                               position(t.span().end())});
    }
    array diagnostics;
    for (const vl::diagnostic& d : s.diagnostics()) {
        diagnostics.push_back(diagnostic(d));
    }
    return object{{"tokens", std::move(tokens)}, {"root", node(s.root())}, {"diagnostics", std::move(diagnostics)}};
}

/// The place of a set variable or a parameter; an override variable has none.
value variable_place(const vw::variable& v) {
    if (auto set = v.as<vw::set_variable>()) {
        return place(set->place());
    }
    if (auto parameter = v.as<vw::parameter>()) {
        return place(parameter->place());
    }
    return nullptr;
}

value variable(const std::optional<vw::variable>& v) {
    if (!v) {
        return nullptr;
    }
    return object{{"id", keep(*v)},
                  {"name", v->name()},
                  {"kind", std::string(vl::to_string(v->kind()))},
                  {"place", variable_place(*v)}};
}

value resolution(const vw::reference_resolution& r) {
    const vw::reference reference = r.reference();
    array shadowed;
    for (const vw::variable& v : r.shadowed()) {
        shadowed.push_back(variable(v));
    }
    return object{
        {"reference", object{{"id", keep(vw::written_value(reference))}, {"place", place(reference.place())}}},
        {"via", steps(r.copy().via())},
        {"winner", variable(r.winner())},
        {"shadowed", std::move(shadowed)}};
}

value written_value(const vw::written_value& v) {
    object out{{"id", keep(v)},
               {"kind", std::string(vl::to_string(v.kind()))},
               {"place", place(v.place())},
               {"text", v.text()}};
    const auto optional = [](const std::optional<vw::written_value>& inner) -> value {
        return inner ? written_value(*inner) : value(nullptr);
    };
    if (auto list = v.as<vw::list>()) {
        array items;
        for (const vw::written_value& item : list->items()) {
            items.push_back(written_value(item));
        }
        out.emplace_back("items", std::move(items));
    } else if (auto slice = v.as<vw::slice>()) {
        out.emplace_back("name", written_value(slice->name()));
        out.emplace_back("start", optional(slice->start()));
        out.emplace_back("end", optional(slice->end()));
    } else if (auto index = v.as<vw::index>()) {
        out.emplace_back("name", written_value(index->name()));
        out.emplace_back("index", written_value(index->index_()));
    } else if (auto reference = v.as<vw::reference>()) {
        array resolutions;
        for (const vw::reference_resolution& r : reference->resolutions()) {
            resolutions.push_back(resolution(r));
        }
        out.emplace_back("declaration", variable(reference->declaration()));
        out.emplace_back("resolutions", std::move(resolutions));
    }
    return out;
}

value written_values(const vl::sequence<vw::written_value>& values) {
    array out;
    for (const vw::written_value& v : values) {
        out.push_back(written_value(v));
    }
    return out;
}

value block(const vw::written_block& b);

value optional_block(const std::optional<vw::written_block>& b) { return b ? block(*b) : value(nullptr); }

value statement(const vw::statement& s) {
    object out{{"id", keep(s)},
               {"kind", std::string(vl::to_string(s.kind()))},
               {"place", place(s.place())},
               {"text", s.text()}};
    if (auto directive = s.as<vw::written_directive>()) {
        out.emplace_back("values", written_values(directive->values()));
        out.emplace_back("block", optional_block(directive->block()));
    } else if (auto extension = s.as<vw::extension_line>()) {
        out.emplace_back("values", written_values(extension->values()));
        out.emplace_back("block", optional_block(extension->block()));
    } else if (auto set = s.as<vw::set_line>()) {
        out.emplace_back("values", written_values(set->values()));
    } else if (auto use = s.as<vw::use_line>()) {
        out.emplace_back("values", written_values(use->values()));
    } else if (auto snippet = s.as<vw::snippet_line>()) {
        out.emplace_back("block", block(snippet->block()));
    }
    return out;
}

value block(const vw::written_block& b) {
    array statements;
    for (const vw::statement& s : b) {
        statements.push_back(statement(s));
    }
    return object{{"id", keep(b)}, {"statements", std::move(statements)}};
}

value copy(const vw::copy& c) { return object{{"place", place(c.statement().place())}, {"via", steps(c.via())}}; }

value texts(const vl::sequence<std::string>& list) {
    array out;
    for (const std::string& text : list) {
        out.emplace_back(text);
    }
    return out;
}

value graph_dump(const vw::document_graph& g) {
    array documents;
    for (const auto& [path, d] : g.documents()) {
        array included_by;
        for (const vw::document_edge& e : d.included_by()) {
            included_by.push_back(copy(e.copy()));
        }
        documents.push_back(object{{"id", keep(d)},
                                   {"path", d.resolved_path()},
                                   {"text", d.text()},
                                   {"savedText", d.saved_text()},
                                   {"syntax", syntax_dump(d.syntax())},
                                   {"block", block(d.block())},
                                   {"includedBy", std::move(included_by)}});
    }
    array edges;
    for (const vw::document_edge& e : g.edges()) {
        edges.push_back(object{{"copy", copy(e.copy())}, {"specs", texts(e.specs())}, {"targets", texts(e.targets())}});
    }
    array variables;
    for (const vw::variable& v : g.variables()) {
        array wins;
        for (const vw::reference_resolution& r : v.wins()) {
            wins.push_back(resolution(r));
        }
        array shadowed_at;
        for (const vw::reference_resolution& r : v.shadowed_at()) {
            shadowed_at.push_back(resolution(r));
        }
        variables.push_back(object{{"id", keep(v)},
                                   {"name", v.name()},
                                   {"kind", std::string(vl::to_string(v.kind()))},
                                   {"place", variable_place(v)},
                                   {"wins", std::move(wins)},
                                   {"shadowedAt", std::move(shadowed_at)}});
    }
    array diagnostics;
    for (const vl::located_diagnostic& d : g.diagnostics()) {
        diagnostics.push_back(located(d));
    }
    return object{{"id", keep(g)},
                  {"documents", std::move(documents)},
                  {"edges", std::move(edges)},
                  {"variables", std::move(variables)},
                  {"diagnostics", std::move(diagnostics)}};
}

// ---- the rendered layer (spec/conformance.md 4.2 to 4.4)

/// A key rule from its data (spec/conformance.md 4.3): the first rule naming the directive (and its parent's name, when
/// the rule gives one) gives the key; no rule: absent.
vr::key_options key_options(const value* rules) {
    if (rules == nullptr) {
        return {};
    }
    struct rule {
        std::string directive;
        std::optional<std::string> parent;
        bool join = false;
        std::string separator;
        std::size_t index = 0;
    };
    std::vector<rule> parsed;
    for (const value& each : array_of(*rules, "key")) {
        rule r;
        r.directive = text_member(each, "directive");
        if (const value* parent = each.find("parent");
            parent != nullptr && !std::holds_alternative<std::nullptr_t>(parent->data)) {
            r.parent = text_of(*parent, "a key rule's parent");
        }
        const array& key = array_of(member_of(each, "key"), "a key rule's key");
        if (key.size() != 2) {
            throw std::runtime_error("a key rule's key is [how, argument]");
        }
        const std::string& how = text_of(key[0], "a key rule's how");
        if (how == "join") {
            r.join = true;
            r.separator = text_of(key[1], "a join separator");
        } else if (how == "value") {
            const auto* index = std::get_if<std::int64_t>(&key[1].data);
            if (index == nullptr || *index < 0) {
                throw std::runtime_error("a value key's index is a non-negative integer");
            }
            r.index = static_cast<std::size_t>(*index);
        } else {
            throw std::runtime_error("unknown key rule: " + how);
        }
        parsed.push_back(std::move(r));
    }
    return {[parsed](const vr::directive& d) -> std::optional<std::string> {
        const std::string name = d.name();
        for (const rule& r : parsed) {
            if (r.directive != name) {
                continue;
            }
            if (r.parent) {
                const std::optional<vr::directive> parent = d.parent();
                if (!parent || parent->name() != *r.parent) {
                    continue;
                }
            }
            const vl::sequence<vw::expanded_value> values = d.values();
            if (!r.join) {
                return r.index < values.size() ? std::optional<std::string>(values.at(r.index).text()) : std::nullopt;
            }
            std::string joined;
            for (std::size_t i = 0; i < values.size(); ++i) {
                joined += (i == 0 ? "" : r.separator) + values.at(i).text();
            }
            return joined;
        }
        return std::nullopt;
    }};
}

value address(const std::optional<vr::address>& a) {
    if (!a) {
        throw std::runtime_error("a directive without an address");
    }
    return object{{"text", a->text()}, {"people", vr::to_string(*a)}};
}

value unreadable(const vl::sequence<vw::unreadable_expansion>& list) {
    array out;
    for (const vw::unreadable_expansion& u : list) {
        out.push_back(object{{"reason", std::string(vl::to_string(u.reason()))}, {"origin", origin(u.origin())}});
    }
    return out;
}

value expanded(const vw::expanded_value& v) {
    const std::optional<vw::written_value> definition = v.definition();
    array chain;
    for (const vw::reference_resolution& r : v.chain()) {
        chain.push_back(resolution(r));
    }
    return object{{"id", keep(v)},
                  {"kind", std::string(vl::to_string(v.kind()))},
                  {"text", v.text()},
                  {"origin", origin(v.origin())},
                  {"definition", definition ? place(definition->place()) : value(nullptr)},
                  {"chain", std::move(chain)}};
}

value directives(const vr::rendered_block& b, const vl::ordered_map<vr::directive, vr::address>& addresses) {
    array out;
    for (const vr::directive& d : b) {
        array values;
        for (const vw::expanded_value& v : d.values()) {
            values.push_back(expanded(v));
        }
        const std::optional<vr::rendered_block> inner = d.block();
        out.push_back(object{{"id", keep(d)},
                             {"name", d.name()},
                             {"address", address(addresses.find(d))},
                             {"origin", origin(d.origin())},
                             {"values", std::move(values)},
                             {"block", inner ? directives(*inner, addresses) : value(nullptr)},
                             {"unreadable", unreadable(d.unreadable())}});
    }
    return out;
}

value render_dump(const vr::rendered& r, const value* rules) {
    const vl::ordered_map<vr::directive, vr::address> addresses = r.addresses(key_options(rules));
    array diagnostics;
    for (const vl::located_diagnostic& d : r.diagnostics()) {
        diagnostics.push_back(located(d));
    }
    return object{{"id", keep(r)},
                  {"block", directives(r.block(), addresses)},
                  {"unreadable", unreadable(r.unreadable())},
                  {"diagnostics", std::move(diagnostics)}};
}

value render(const value& request) {
    const kept target = find(text_member(request, "graph"));
    const auto* graph = std::get_if<vw::document_graph>(&target);
    if (graph == nullptr) {
        // C++'s render takes a document graph by type, so a call with anything else does not compile (design.md
        // finding F1): the adapter reports that refusal as the argument type error the case expects (spec 7.0).
        throw vl::argument_type_error("render(): argument 'graph' must be a document graph");
    }
    return render_dump(vr::render(*graph), request.find("key"));
}

value diff(const value& request) {
    const vr::rendered before = get<vr::rendered>(text_member(request, "before"));
    const vr::rendered after = get<vr::rendered>(text_member(request, "after"));
    array out;
    for (const vr::change& c : before.diff(after, key_options(request.find("key")))) {
        out.push_back(object{{"kind", std::string(vl::to_string(c.kind()))}, {"address", address(c.address())}});
    }
    return out;
}

/// A reader's result, neutral (spec/conformance.md 4.4): negative zero as "-0", a list's items by their text.
value read(const value& request) {
    const vw::expanded_value v = get<vw::expanded_value>(text_member(request, "value"));
    const std::string_view reader = adapter::shapes::spelling(text_member(request, "reader"));
    if (reader == "word") {
        return object{{"text", v.word()}};
    }
    if (reader == "string") {
        return object{{"text", v.string()}};
    }
    if (reader == "number") {
        const double n = v.number();
        return object{{"number", n == 0 && std::signbit(n) ? value("-0") : value(n)}};
    }
    if (reader == "integer") {
        return object{{"number", v.integer()}};
    }
    if (reader == "boolean") {
        return object{{"boolean", v.boolean()}};
    }
    if (reader == "list") {
        array items;
        for (const vw::expanded_value& item : v.list()) {
            items.push_back(object{{"value", item.text()}});
        }
        return object{{"list", std::move(items)}};
    }
    if (reader == "slice") {
        const std::variant<vw::slice_value, vw::index_value> s = v.slice();
        if (const auto* index = std::get_if<vw::index_value>(&s)) {
            return object{{"index", array{index->name(), index->index()}}};
        }
        const vw::slice_value& slice = std::get<vw::slice_value>(s);
        const auto bound = [](std::optional<std::int64_t> b) { return b ? value(*b) : value(nullptr); };
        return object{{"slice", array{slice.name(), bound(slice.start()), bound(slice.end())}}};
    }
    throw std::runtime_error("no reader '" + std::string(reader) + "'");
}

/// The object's people form (contract 2): this binding's to_string.
value print(const value& request) {
    const kept target = find(text_member(request, "target"));
    return std::visit(
        [](const auto& o) -> value {
            if constexpr (requires { vl::to_string(o); }) {
                return value(std::string(vl::to_string(o)));
            } else {
                throw std::runtime_error("that object has no people form");
            }
        },
        target);
}

value format(const value& request) {
    const vl::located_diagnostic d = get<vl::located_diagnostic>(text_member(request, "diagnostic"));
    if (const value* graph = request.find("graph")) {
        return value(vw::format_diagnostic(d, get<vw::document_graph>(text_of(*graph, "graph"))));
    }
    return value(vw::format_diagnostic(d));
}

/// The text cut at two byte offsets, as std::string slices (clamped to the text, as a slice of a string is).
value cut(const value& request) {
    const std::string& text = text_member(request, "text");
    const auto offset = [&](std::string_view name) {
        const auto* n = std::get_if<std::int64_t>(&member_of(request, name).data);
        if (n == nullptr) {
            throw std::runtime_error(std::string(name) + " is not an integer");
        }
        return static_cast<std::size_t>(std::clamp<std::int64_t>(*n, 0, static_cast<std::int64_t>(text.size())));
    };
    const std::size_t start = offset("start");
    const std::size_t end = offset("end");
    return value(start < end ? text.substr(start, end - start) : std::string());
}

// ---- edits: a member by its spec name, in this binding's spelling, called on the object the id names

/// The edit's result: the handles a member returned (their ids and texts).
template <class Handle>
value handles(const vl::sequence<Handle>& made) {
    array out;
    for (const Handle& h : made) {
        out.push_back(object{{"id", keep(h)}, {"text", h.text()}});
    }
    return object{{"handles", std::move(out)}};
}

value edited() { return object{}; }

/// Every text an edit takes is config text: the driver's texts go through the binding's own text() (spec 6.9).
vl::config_text config(const array& args, std::size_t at) {
    if (at >= args.size()) {
        throw std::runtime_error("missing argument " + std::to_string(at));
    }
    return vl::text(text_of(args[at], "a text argument"));
}

const std::string& name_argument(const array& args, std::size_t at) {
    if (at >= args.size()) {
        throw std::runtime_error("missing argument " + std::to_string(at));
    }
    return text_of(args[at], "a name argument");
}

[[noreturn]] void no_member(std::string_view name) {
    throw std::runtime_error("no member '" + std::string(name) + "' on that object");
}

value edit_statement(const vw::statement& s, std::string_view name, const array& args) {
    if (name == "set") {
        if (auto d = s.as<vw::written_directive>()) {
            d->set(config(args, 0));
        } else if (auto e = s.as<vw::extension_line>()) {
            e->set(config(args, 0));
        } else if (auto line = s.as<vw::set_line>()) {
            line->set(config(args, 0));
        } else if (auto use = s.as<vw::use_line>()) {
            use->set(config(args, 0));
        } else {
            no_member(name);
        }
        return edited();
    }
    if (name == "replace_with_text") {
        return handles(s.replace_with_text(config(args, 0)));
    }
    if (name == "remove") {
        s.remove();
        return edited();
    }
    if (name == "rename") {
        auto d = s.as<vw::written_directive>();
        if (!d) {
            no_member(name);
        }
        d->rename(name_argument(args, 0));
        return edited();
    }
    if (name == "insert_before") {
        return handles(s.insert_before(config(args, 0)));
    }
    if (name == "insert_after") {
        return handles(s.insert_after(config(args, 0)));
    }
    no_member(name);
}

value edit_value(const vw::written_value& v, std::string_view name, const array& args) {
    if (name == "set") {
        v.set(config(args, 0));
        return edited();
    }
    if (name == "replace_with_text") {
        return handles(v.replace_with_text(config(args, 0)));
    }
    if (name == "remove") {
        v.remove();
        return edited();
    }
    no_member(name);
}

value edit_variable(const vw::variable& v, std::string_view name, const array& args) {
    if (name == "set") {
        auto set = v.as<vw::set_variable>();
        if (!set) {
            no_member(name);
        }
        set->set(config(args, 0));
        return edited();
    }
    if (name == "rename") {
        if (auto set = v.as<vw::set_variable>()) {
            set->rename(name_argument(args, 0));
        } else if (auto parameter = v.as<vw::parameter>()) {
            parameter->rename(name_argument(args, 0));
        } else {
            no_member(name);
        }
        return edited();
    }
    no_member(name);
}

value edit_block(const vw::written_block& b, std::string_view name, const array& args) {
    if (name == "insert_statements") {
        if (args.empty()) {
            throw std::runtime_error("missing argument 0");
        }
        const auto* index = std::get_if<std::int64_t>(&args[0].data);
        if (index == nullptr) {
            throw std::runtime_error("insert statements: the index is not an integer");
        }
        return handles(b.insert_statements(*index, config(args, 1)));
    }
    if (name == "add_statements") {
        return handles(b.add_statements(config(args, 0)));
    }
    no_member(name);
}

value edit(const value& request) {
    const kept target = find(text_member(request, "target"));
    const std::string_view name = adapter::shapes::spelling(text_member(request, "member"));
    const array& args = array_of(member_of(request, "args"), "args");
    if (const auto* s = std::get_if<vw::statement>(&target)) {
        return edit_statement(*s, name, args);
    }
    if (const auto* v = std::get_if<vw::written_value>(&target)) {
        return edit_value(*v, name, args);
    }
    if (const auto* v = std::get_if<vw::variable>(&target)) {
        return edit_variable(*v, name, args);
    }
    if (const auto* b = std::get_if<vw::written_block>(&target)) {
        return edit_block(*b, name, args);
    }
    if (const auto* d = std::get_if<vw::document>(&target)) {
        if (name != "replace_with_text") {
            no_member(name);
        }
        d->replace_with_text(config(args, 0));
        return edited();
    }
    if (const auto* g = std::get_if<vw::document_graph>(&target)) {
        if (name != "set_override") {
            no_member(name);
        }
        const bool absent = args.size() < 2 || std::holds_alternative<std::nullptr_t>(args[1].data);
        g->set_override(name_argument(args, 0),
                        absent ? std::nullopt : std::optional<vl::config_text>(config(args, 1)));
        return edited();
    }
    no_member(name);
}

// ---- load and save

value load(const value& request) {
    auto files = std::make_shared<vl::ordered_map<std::string, std::string>>();
    for (const auto& [path, text] : object_of(member_of(request, "files"), "files")) {
        files->insert_or_assign(path, text_of(text, "a file's text"));
    }
    vw::processor_options options{vl::memory_source(files), {}};
    for (const value& extension : array_of(member_of(request, "extensions"), "extensions")) {
        if (text_of(extension, "an extension") == "include") {
            options.extensions = {vl::extensions::include()};
        }
    }
    vw::load_options load_options;
    if (const value* overrides = request.find("overrides")) {
        for (const auto& [name, text] : object_of(*overrides, "overrides")) {
            load_options.overrides.insert_or_assign(name, vl::text(text_of(text, "an override's text")));
        }
    }
    const vw::processor processor(std::move(options));
    return object{{"graph", keep(processor.load(text_member(request, "root"), std::move(load_options)))}};
}

/// A writer that records each batch it is handed (the protocol's save without disk).
class recording_writer final : public vl::document_writer {
public:
    void write(vl::sequence<vl::file_write> files) const override {
        array batch;
        for (const vl::file_write& file : files) {
            batch.push_back(array{file.resolved_path(), file.text()});
        }
        batches->push_back(std::move(batch));
    }
    std::shared_ptr<array> batches = std::make_shared<array>();
};

value save(const value& request) {
    const vw::document_graph g = get<vw::document_graph>(text_member(request, "graph"));
    if (const value* disk = request.find("disk")) {
        auto files = std::make_shared<vl::ordered_map<std::string, std::string>>();
        for (const auto& [path, text] : object_of(*disk, "disk")) {
            files->insert_or_assign(path, text_of(text, "a file's text"));
        }
        g.save(vl::memory_writer(files));
        std::vector<std::pair<std::string, std::string>> sorted;
        for (const auto& [path, text] : *files) {
            sorted.emplace_back(path, text);
        }
        std::sort(sorted.begin(), sorted.end());
        array out;
        for (const auto& [path, text] : sorted) {
            out.push_back(array{path, text});
        }
        return object{{"files", std::move(out)}};
    }
    auto writer = std::make_shared<recording_writer>();
    g.save(writer);
    return object{{"batches", *writer->batches}};
}

/// The ok result of one request, or nullopt for an op this level does not support.
std::optional<value> answer(const std::string& op, const value& request) {
    if (op == "hello") {
        return object{{"protocol", adapter::shapes::protocol}, {"binding", "cpp"}, {"unit", "byte"}, {"level", level}};
    }
    if (op == "parse") {
        return syntax_dump(vl::syntax::parse(text_member(request, "text")));
    }
    if (op == "load") {
        return load(request);
    }
    if (op == "graph") {
        return graph_dump(get<vw::document_graph>(text_member(request, "graph")));
    }
    if (op == "edit") {
        return edit(request);
    }
    if (op == "save") {
        return save(request);
    }
    if (op == "render") {
        return render(request);
    }
    if (op == "diff") {
        return diff(request);
    }
    if (op == "read") {
        return read(request);
    }
    if (op == "print") {
        return print(request);
    }
    if (op == "format") {
        return format(request);
    }
    if (op == "cut") {
        return cut(request);
    }
    if (op == "quote") {
        const vl::config_text quoted = vl::quote(text_member(request, "text"));
        return value(std::string(quoted.view()));
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
    if (const auto* e = dynamic_cast<const vl::diagnostic_error*>(&error)) {
        body.emplace_back("code", code_text(e->diagnostic().code()));
    }
    if (const auto* e = dynamic_cast<const vl::bad_text_error*>(&error)) {
        array diagnostics;
        for (const vl::diagnostic& d : e->diagnostics()) {
            diagnostics.push_back(diagnostic(d));
        }
        body.emplace_back("diagnostics", std::move(diagnostics));
    }
    if (const auto* e = dynamic_cast<const vl::read_error*>(&error)) {
        body.emplace_back("paths", texts(e->paths()));
    } else if (const auto* s = dynamic_cast<const vl::save_error*>(&error)) {
        body.emplace_back("paths", texts(s->paths()));
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
