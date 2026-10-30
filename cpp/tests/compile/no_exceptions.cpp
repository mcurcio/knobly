// The syntax and written layers compiled with exceptions and RTTI off (frozen-m1.md section 5.1, frozen-m2.md 3.3
// rule 7): the parser, the written layer and every definition they reach compile without throw, try or typeid
// outside detail/raise.hpp and collect's guarded try, and detail::raise takes its abort branch. Compiled, never
// linked.
#include <villanelle/syntax.hpp>
#include <villanelle/written.hpp>

#if !VILLANELLE_HEADER_ONLY
#include <villanelle/implementation.hpp>
#endif

#include <memory>
#include <string>
#include <string_view>

// Odr-uses each syntax function, so every template and inline definition behind them is compiled here.
villanelle::syntax::syntax parse_without_exceptions(std::string_view text);
villanelle::syntax::syntax parse_without_exceptions(std::string_view text) {
    villanelle::syntax::syntax parsed = villanelle::syntax::parse(text);
    const villanelle::syntax::token_range all(0, static_cast<std::int64_t>(parsed.tokens().size()));
    static_cast<void>(villanelle::syntax::span_of(parsed, all));
    static_cast<void>(villanelle::syntax::text_of(parsed, all));
    for (const villanelle::diagnostic& d : parsed.diagnostics()) {
        static_cast<void>(villanelle::to_string(d));
    }
    return parsed;
}

// A load, an edit, a walk, the expansion with a reader under collect, and a save: the written layer's paths.
std::string written_without_exceptions(std::shared_ptr<villanelle::ordered_map<std::string, std::string>> files);
std::string written_without_exceptions(std::shared_ptr<villanelle::ordered_map<std::string, std::string>> files) {
    namespace vw = villanelle::written;
    const vw::document_graph graph = vw::processor({villanelle::memory_source(files), {}}).load("main.conf");
    graph.root().block().add_statements(villanelle::text("x 1;"));
    std::string out;
    for (const vw::statement& s : graph.root().block().walk()) {
        out += s.text();
    }
    const villanelle::diagnostics sink(graph.diagnostics());
    static_cast<void>(sink.collect([&] { return graph.expand().block().at(0).values().at(0).integer(); }));
    graph.save(villanelle::memory_writer(files));
    return out + vw::format_diagnostic(graph.diagnostics().at(0), graph);
}
