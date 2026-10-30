// The syntax and written layers compiled with exceptions and RTTI off (frozen-m1.md section 5.1, frozen-m2.md 3.3
// rule 7): the parser, the written layer and every definition they reach compile without throw, try or typeid
// outside detail/raise.hpp and collect's guarded try, and detail::raise takes its abort branch. Compiled, never
// linked.
#include <knobly/syntax.hpp>
#include <knobly/written.hpp>

#if !KNOBLY_HEADER_ONLY
#include <knobly/implementation.hpp>
#endif

#include <memory>
#include <string>
#include <string_view>

// Odr-uses each syntax function, so every template and inline definition behind them is compiled here.
knobly::syntax::syntax parse_without_exceptions(std::string_view text);
knobly::syntax::syntax parse_without_exceptions(std::string_view text) {
    knobly::syntax::syntax parsed = knobly::syntax::parse(text);
    const knobly::syntax::token_range all(0, static_cast<std::int64_t>(parsed.tokens().size()));
    static_cast<void>(knobly::syntax::span_of(parsed, all));
    static_cast<void>(knobly::syntax::text_of(parsed, all));
    for (const knobly::diagnostic& d : parsed.diagnostics()) {
        static_cast<void>(knobly::to_string(d));
    }
    return parsed;
}

// A load, an edit, a walk, the expansion with a reader under collect, and a save: the written layer's paths.
std::string written_without_exceptions(std::shared_ptr<knobly::ordered_map<std::string, std::string>> files);
std::string written_without_exceptions(std::shared_ptr<knobly::ordered_map<std::string, std::string>> files) {
    namespace vw = knobly::written;
    const vw::document_graph graph = vw::processor({knobly::memory_source(files), {}}).load("main.conf");
    graph.root().block().add_statements(knobly::text("x 1;"));
    std::string out;
    for (const vw::statement& s : graph.root().block().walk()) {
        out += s.text();
    }
    const knobly::diagnostics sink(graph.diagnostics());
    static_cast<void>(sink.collect([&] { return graph.expand().block().at(0).values().at(0).integer(); }));
    graph.save(knobly::memory_writer(files));
    return out + vw::format_diagnostic(graph.diagnostics().at(0), graph);
}
