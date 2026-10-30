// The hand-written half of the syntax layer (design.md 1.5; frozen-m1.md section 3.2): the token loop, the error
// codes (spec 2.4), per-statement recovery (spec 3.2), the tree hooks and the nesting guard. Everything grammar-shaped
// is in the generated parser.gen.hpp (tools/parser/gen.py), whose generated_parser this class derives from.
// SKELETON: the hooks are declared, not defined; Slice T defines them and syntax::parse, span_of and text_of.
#ifndef VILLANELLE_DETAIL_SYNTAX_PARSE_HPP
#define VILLANELLE_DETAIL_SYNTAX_PARSE_HPP

#include <cstddef>

#include <villanelle/detail/syntax/parser.gen.hpp>
#include <villanelle/detail/text_in.hpp>
#include <villanelle/kinds.hpp>
#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace syntax::detail {

class parser : public generated_parser<parser> {
    friend class generated_parser<parser>;

public:
    // ---- the hooks the generated parser calls (frozen-m1.md section 3.2)
    tk la(std::size_t i) const noexcept;    // the kind i tokens ahead; tk::end_of_text past the end
    std::size_t pos() const noexcept;       // the current token index
    bool match(tk kind);                    // consume `kind` or report at pos(); false on a mismatch
    bool fail(std::size_t at);              // report an error at token index `at`; always false
    void open_node(::villanelle::node_kind kind);  // a rule annotated "cst: <kind>" starts
    void close_node();                      // that rule succeeded
    void fail_node();                       // that rule failed (a directive without its block joins the error node)
    bool recover_document();                // spec 3.2 recovery, called when the rule's own body fails
    bool recover_statements();
    bool recover_block();
};

}  // namespace syntax::detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_SYNTAX_PARSE_HPP
