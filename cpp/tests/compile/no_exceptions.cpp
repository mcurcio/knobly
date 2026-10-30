// The syntax layer compiled with exceptions and RTTI off (frozen-m1.md section 5.1): the parser and every
// definition it reaches compile without throw, try or typeid, and detail::raise takes its abort branch. Compiled,
// never linked.
#include <villanelle/syntax.hpp>

#if !VILLANELLE_HEADER_ONLY
#include <villanelle/implementation.hpp>
#endif

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
