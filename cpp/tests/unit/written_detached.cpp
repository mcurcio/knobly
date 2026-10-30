// Detached handles (contract 4.3; design.md 2.3): every member but kind() of a removed statement, value or variable
// raises detached_error, before any other check; and a handle shares ownership of its graph, which lives while any
// handle of it does (owner, 2026-10-30, Q2).
#include <knobly/written.hpp>

#include <optional>
#include <string>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = knobly;
namespace vw = knobly::written;

TEST_CASE("every member of a removed directive raises detached_error; kind() works", "[detached]") {
    const vw::document_graph graph = fixture::load("x [1, 2] {\n    y;\n}\nz;\n");
    const vw::statement s = fixture::top(graph, 0);
    const vw::written_directive d = *s.as<vw::written_directive>();
    s.remove();
    CHECK(s.kind() == vl::statement_kind::directive);
    CHECK(s.as<vw::written_directive>().has_value());  // as<V>() reads only kind()
    CHECK_THROWS_AS(s.document(), vl::detached_error);
    CHECK_THROWS_AS(s.parent(), vl::detached_error);
    CHECK_THROWS_AS(s.place(), vl::detached_error);
    CHECK_THROWS_AS(s.text(), vl::detached_error);
    CHECK_THROWS_AS(s.copies(), vl::detached_error);
    CHECK_THROWS_AS(s.replace_with_text(vl::text("a;")), vl::detached_error);
    CHECK_THROWS_AS(s.remove(), vl::detached_error);
    CHECK_THROWS_AS(s.insert_before(vl::text("a;")), vl::detached_error);
    CHECK_THROWS_AS(s.insert_after(vl::text("a;")), vl::detached_error);
    CHECK_THROWS_AS(d.name(), vl::detached_error);
    CHECK_THROWS_AS(d.values(), vl::detached_error);
    CHECK_THROWS_AS(d.block(), vl::detached_error);
    // Detached comes before any other check: a bad name or bad text still raises detached_error.
    CHECK_THROWS_AS(d.rename("not a name"), vl::detached_error);
    CHECK_THROWS_AS(d.set(vl::text("[")), vl::detached_error);
    CHECK(graph.root().text() == "z;\n");
}

TEST_CASE("the language statements' own members raise detached_error too", "[detached]") {
    const vw::document_graph graph =
        fixture::load("@set $a 1;\n@snippet s $p {\n    q $p;\n}\n@use s 2;\n@include \"x\";\n");
    const vw::set_line set = *fixture::top(graph, 0).as<vw::set_line>();
    const vw::snippet_line snippet = *fixture::top(graph, 1).as<vw::snippet_line>();
    const vw::use_line use = *fixture::top(graph, 2).as<vw::use_line>();
    graph.root().replace_with_text(vl::text("other;\n"));
    CHECK(set.kind() == vl::statement_kind::set);
    CHECK_THROWS_AS(set.variable(), vl::detached_error);
    CHECK_THROWS_AS(set.values(), vl::detached_error);
    CHECK_THROWS_AS(set.set(vl::text("2")), vl::detached_error);
    CHECK_THROWS_AS(snippet.name(), vl::detached_error);
    CHECK_THROWS_AS(snippet.parameters(), vl::detached_error);
    CHECK_THROWS_AS(snippet.block(), vl::detached_error);
    CHECK_THROWS_AS(use.snippet_name(), vl::detached_error);
    CHECK_THROWS_AS(use.snippet(), vl::detached_error);
    CHECK_THROWS_AS(use.snippets(), vl::detached_error);
    CHECK_THROWS_AS(use.values(), vl::detached_error);
    CHECK_THROWS_AS(use.set(vl::text("3")), vl::detached_error);
}

TEST_CASE("every member of a removed value raises detached_error; kind() works", "[detached]") {
    const vw::document_graph graph = fixture::load("@set $v 1;\nx [1, 2] s[0~1] i[2] $v;\n");
    const vw::written_directive x = *fixture::top(graph, 1).as<vw::written_directive>();
    const vw::list list = *x.values().at(0).as<vw::list>();
    const vw::written_value item = list.items().at(0);
    const vw::slice slice = *x.values().at(1).as<vw::slice>();
    const vw::index index = *x.values().at(2).as<vw::index>();
    const vw::reference reference = *x.values().at(3).as<vw::reference>();
    x.set(vl::text("plain"));
    for (const vw::written_value& v : {vw::written_value(list), item, vw::written_value(slice),
                                       vw::written_value(index), vw::written_value(reference)}) {
        CHECK_THROWS_AS(v.text(), vl::detached_error);
        CHECK_THROWS_AS(v.place(), vl::detached_error);
        CHECK_THROWS_AS(v.statement(), vl::detached_error);
        CHECK_THROWS_AS(v.list(), vl::detached_error);
        CHECK_THROWS_AS(v.set(vl::text("[")), vl::detached_error);
        CHECK_THROWS_AS(v.replace_with_text(vl::text("1")), vl::detached_error);
        CHECK_THROWS_AS(v.remove(), vl::detached_error);
    }
    CHECK(list.kind() == vl::value_kind::list);
    CHECK(item.kind() == vl::value_kind::word);
    CHECK_THROWS_AS(list.items(), vl::detached_error);
    CHECK_THROWS_AS(list.list_(), vl::detached_error);
    CHECK_THROWS_AS(slice.name(), vl::detached_error);
    CHECK_THROWS_AS(slice.start(), vl::detached_error);
    CHECK_THROWS_AS(slice.end(), vl::detached_error);
    CHECK_THROWS_AS(index.name(), vl::detached_error);
    CHECK_THROWS_AS(index.index_(), vl::detached_error);
    CHECK_THROWS_AS(reference.name(), vl::detached_error);
    CHECK_THROWS_AS(reference.declaration(), vl::detached_error);
    CHECK_THROWS_AS(reference.resolutions(), vl::detached_error);
}

TEST_CASE("every member of a removed variable raises detached_error; kind() works", "[detached]") {
    const vw::document_graph graph = fixture::load("@set $a 1;\n@snippet s $p {\n    q $p;\n}\n");
    const vw::variable set = graph.variables().at(0);
    const vw::variable parameter = graph.variables().at(1);
    const vw::set_variable set_variable = *set.as<vw::set_variable>();
    const vw::parameter param = *parameter.as<vw::parameter>();
    fixture::top(graph, 0).remove();
    // Renaming the parameter's line away removes the parameter's token: the parameter is detached.
    fixture::top(graph, 0).as<vw::snippet_line>()->replace_with_text(vl::text("@snippet s {\n    q;\n}"));
    for (const vw::variable& v : {set, parameter}) {
        CHECK_THROWS_AS(v.name(), vl::detached_error);
        CHECK_THROWS_AS(v.references(), vl::detached_error);
        CHECK_THROWS_AS(v.wins(), vl::detached_error);
        CHECK_THROWS_AS(v.shadowed_at(), vl::detached_error);
    }
    CHECK(set.kind() == vl::variable_kind::set);
    CHECK(parameter.kind() == vl::variable_kind::parameter);
    CHECK_THROWS_AS(set_variable.place(), vl::detached_error);
    CHECK_THROWS_AS(set_variable.line(), vl::detached_error);
    CHECK_THROWS_AS(set_variable.rename("b"), vl::detached_error);
    CHECK_THROWS_AS(set_variable.set(vl::text("2")), vl::detached_error);
    CHECK_THROWS_AS(param.place(), vl::detached_error);
    CHECK_THROWS_AS(param.line(), vl::detached_error);
    CHECK_THROWS_AS(param.rename("r"), vl::detached_error);
}

TEST_CASE("the graph outlives the last other handle", "[detached][ownership]") {
    std::optional<vw::written_value> value;
    std::optional<vw::statement> removed;
    {
        const vw::document_graph graph = fixture::load("keep 1 2;\ngone;\n");
        value = fixture::top(graph, 0).as<vw::written_directive>()->values().at(1);
        removed = fixture::top(graph, 1);
        removed->remove();
    }  // the graph handle is gone; the value's view holds the graph
    CHECK(value->text() == "2");
    CHECK(value->statement().document().text() == "keep 1 2;\n");
    value->set(vl::text("3"));
    CHECK(value->statement().document().text() == "keep 1 3;\n");
    CHECK(removed->kind() == vl::statement_kind::directive);  // a detached handle keeps the graph alive too
    CHECK_THROWS_AS(removed->text(), vl::detached_error);
    value.reset();
    removed.reset();  // the last handle: the graph is freed here (AddressSanitizer checks the frees)
}

TEST_CASE("binding records (copies, resolutions, expanded values) keep the graph alive", "[detached][ownership]") {
    std::optional<vw::expanded_value> expanded;
    std::optional<vw::copy> copy;
    {
        const vw::document_graph graph = fixture::load("@set $v 7;\nx $v;\n");
        copy = fixture::top(graph, 1).copies().at(0);
        expanded = graph.expand().block().at(0).values().at(0);
        fixture::top(graph, 1).as<vw::written_directive>()->set(vl::text("8"));  // a new binding; the old one lives on
    }
    CHECK(expanded->text() == "7");
    CHECK(expanded->integer() == 7);
    CHECK(expanded->chain().at(0).winner()->name() == "v");
    CHECK(copy->statement().text() == "x 8;");
}
