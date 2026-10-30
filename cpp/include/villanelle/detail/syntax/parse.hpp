// The hand-written half of the syntax layer (design.md 1.5; frozen-m1.md section 3.2): the token loop, the error
// codes (spec 2.4), per-statement recovery (spec 3.2), the tree hooks and the nesting guard. Everything grammar-shaped
// is in the generated parser.gen.hpp (tools/parser/gen.py), whose generated_parser this class derives from.
// No throw, try or RTTI: the syntax layer compiles with -fno-exceptions -fno-rtti, and parse is total.
#ifndef VILLANELLE_DETAIL_SYNTAX_PARSE_HPP
#define VILLANELLE_DETAIL_SYNTAX_PARSE_HPP

#include <cstddef>
#include <cstdio>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <villanelle/codes.hpp>
#include <villanelle/detail/syntax/parser.gen.hpp>
#include <villanelle/detail/text_in.hpp>
#include <villanelle/kinds.hpp>
#include <villanelle/limits.hpp>
#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace syntax::detail {

inline constexpr std::size_t npos = static_cast<std::size_t>(-1);

/// One token as the lexer finds it: its kind and its byte range in the text.
struct raw_token {
    tk kind;
    std::size_t start;
    std::size_t end;
};

/// One node as the parser builds it: a token range, half-open.
struct raw_node {
    ::villanelle::node_kind kind;
    std::size_t start;
    std::size_t end;
    std::vector<raw_node> children;
};

/// One problem at token index `at` (the token count for the end of the text).
struct raw_diagnostic {
    ::villanelle::diagnostic_code code;
    std::size_t at;
    std::string message;
};

/// The token loop: the generated longest match at each byte; a byte that does not decode, or where no token
/// starts, is one BAD_CHAR (of the whole code point when it decodes).
inline std::vector<raw_token> lex(std::string_view text) {
    std::vector<raw_token> tokens;
    for (std::size_t at = 0; at < text.size();) {
        auto [kind, end] = lex_longest(text, at, ::villanelle::detail::decode_utf8);
        if (kind < 0) {
            char32_t code_point = 0;
            const std::size_t length = ::villanelle::detail::decode_utf8(text, at, code_point);
            kind = static_cast<int>(tk::BAD_CHAR);
            end = at + (length != 0 ? length : 1);
        }
        tokens.push_back({static_cast<tk>(kind), at, end});
        at = end;
    }
    return tokens;
}

inline bool is_value(tk kind) noexcept {
    return kind == tk::WORD || kind == tk::AT_WORD || kind == tk::INTEGER || kind == tk::DIGIT_WORD ||
           kind == tk::STRING || kind == tk::VARIABLE;
}

inline bool is_slice_name(tk kind) noexcept { return kind == tk::WORD || kind == tk::AT_WORD || kind == tk::VARIABLE; }

/// Spec 2.4: the code of a syntax error at token `at` in the statement starting at token `start`; the first rule
/// that applies wins.
inline ::villanelle::diagnostic_code classify(const std::vector<raw_token>& tokens, std::size_t at, std::size_t start,
                                              bool in_block) {
    using code = ::villanelle::diagnostic_code;
    std::vector<bool> brackets;  // per open '[': whether it opens a slice (it touches a slice name)
    int braces = 0;
    bool closes_value = false;  // the token before `at` is a ']' that closed a list or slice
    for (std::size_t i = start; i < at; ++i) {
        const tk kind = tokens[i].kind;
        closes_value = false;
        if (kind == tk::LBRACK) {
            brackets.push_back(i > 0 && is_slice_name(tokens[i - 1].kind));
        } else if (kind == tk::RBRACK) {
            closes_value = !brackets.empty();
            if (!brackets.empty()) {
                brackets.pop_back();
            }
        } else if (kind == tk::LBRACE) {
            ++braces;
        } else if (kind == tk::RBRACE && braces > 0) {
            --braces;
        }
    }
    const bool end_of_text = at >= tokens.size();
    const tk kind = end_of_text ? tk::end_of_text : tokens[at].kind;
    const bool in_bracket = !brackets.empty();
    const bool in_slice = in_bracket && brackets.back();
    const tk before = at > 0 ? tokens[at - 1].kind : tk::end_of_text;
    if (kind == tk::BAD_CHAR || (kind == tk::BOM && at > 0)) {
        return code::unexpected_character;
    }
    if (kind == tk::LONE_DOLLAR) {
        return code::lone_dollar;
    }
    if (kind == tk::UNTERMINATED_STRING) {
        return code::unterminated_string;
    }
    if (kind == tk::BAD_ESCAPE) {
        return code::bad_escape;
    }
    if (in_slice) {
        return code::bad_slice;
    }
    if (kind == tk::RBRACK || (in_bracket && (kind == tk::RBRACE || end_of_text))) {
        return code::expected_closing_bracket;
    }
    if (end_of_text && (in_block || braces > 0)) {
        return code::expected_closing_brace;
    }
    if (!end_of_text && (is_value(kind) || kind == tk::LBRACK) && at > 0 &&
        (is_value(before) || (before == tk::RBRACK && closes_value))) {
        return code::values_touch;
    }
    return code::unexpected_token;
}

/// The nesting guard (E2010), run before parsing so the recursive parser never nests deeper than the limit: the
/// index of the first '{' or '[' past the limit, or npos.
inline std::size_t nesting_overflow(const std::vector<raw_token>& tokens) noexcept {
    std::size_t depth = 0;
    for (std::size_t i = 0; i < tokens.size(); ++i) {
        const tk kind = tokens[i].kind;
        if (kind == tk::LBRACE || kind == tk::LBRACK) {
            if (++depth > static_cast<std::size_t>(::villanelle::syntax::max_nesting)) {
                return i;
            }
        } else if ((kind == tk::RBRACE || kind == tk::RBRACK) && depth > 0) {
            --depth;
        }
    }
    return npos;
}

/// A token's text as a diagnostic's detail shows it: in double quotes, with JSON's escapes.
inline std::string quoted(std::string_view text) {
    std::string out = "\"";
    for (const char c : text) {
        const auto byte = static_cast<unsigned char>(c);
        if (c == '"' || c == '\\') {
            out += '\\';
            out += c;
        } else if (c == '\n') {
            out += "\\n";
        } else if (c == '\r') {
            out += "\\r";
        } else if (c == '\t') {
            out += "\\t";
        } else if (byte < 0x20) {
            char escape[8];
            std::snprintf(escape, sizeof escape, "\\u%04x", static_cast<unsigned>(byte));
            out += escape;
        } else {
            out += c;
        }
    }
    out += '"';
    return out;
}

/// The generated parser with spec 3.2's policy: the hooks build the tree, report each statement's first error
/// and recover per statement.
class parser : public generated_parser<parser> {
    friend class generated_parser<parser>;

    /// The state of one statements list (the document's, or a block's).
    struct level {
        std::size_t open_directive = npos;  // the first token of the directive being parsed
        std::size_t failed = npos;          // the first token of the directive that just failed
        bool discarded = false;             // that directive had no block, so it joins the error node
    };

public:
    parser(std::string_view text, const std::vector<raw_token>& tokens) : text_(text), tokens_(tokens) {}

    /// The tree and the diagnostics, after r_document().
    raw_node take_root() { return std::move(root_); }
    std::vector<raw_diagnostic> take_diagnostics() { return std::move(diagnostics_); }

    // ---- the hooks the generated parser calls (frozen-m1.md section 3.2)

    /// The kind i tokens ahead; tk::end_of_text past the end.
    tk la(std::size_t i) const noexcept { return pos_ + i < tokens_.size() ? tokens_[pos_ + i].kind : tk::end_of_text; }
    /// The current token index.
    std::size_t pos() const noexcept { return pos_; }
    /// Consume a token of `kind` (end_of_text is matched, not consumed), or report at pos() and return false.
    bool match(tk kind) {
        if (la(0) != kind) {
            return fail(pos_);
        }
        if (kind != tk::end_of_text) {
            ++pos_;
        }
        in_error_ = false;  // a matched token ends the bad statement's silence
        return true;
    }
    /// Report a syntax error at token index `at`; always false.
    bool fail(std::size_t at) {
        report(at);
        return false;
    }
    /// A rule annotated "cst: <kind>" starts.
    void open_node(::villanelle::node_kind kind) {
        open_.push_back({kind, pos_, pos_, {}});
        if (kind == ::villanelle::node_kind::directive) {
            levels_.back().open_directive = pos_;
        } else if (kind == ::villanelle::node_kind::block) {
            levels_.push_back({});
        }
    }
    /// That rule succeeded.
    void close_node() {
        raw_node done = std::move(open_.back());
        open_.pop_back();
        done.end = pos_;
        if (done.kind == ::villanelle::node_kind::directive) {
            levels_.back().open_directive = npos;
        } else if (done.kind == ::villanelle::node_kind::block) {
            levels_.pop_back();
        }
        attach(std::move(done));
    }
    /// That rule failed. A directive whose block was not opened is dropped: its tokens join the error node recovery
    /// makes. Any other node (a directive with its block, an unclosed block, a list, a slice) keeps its node.
    void fail_node() {
        raw_node& failed = open_.back();
        if (failed.kind == ::villanelle::node_kind::directive) {
            level& here = levels_.back();
            here.open_directive = npos;
            here.failed = failed.start;
            bool has_block = false;
            for (const raw_node& child : failed.children) {
                has_block = has_block || child.kind == ::villanelle::node_kind::block;
            }
            here.discarded = !has_block;
            if (!has_block) {
                open_.pop_back();
                return;
            }
        }
        close_node();
    }
    /// Spec 3.2 recovery for a statements list: skip the bad statement, then read on.
    bool recover_statements() {
        for (;;) {
            skip();
            if (la(0) == tk::end_of_text || la(0) == tk::RBRACE) {
                return true;
            }
            if (b_statements()) {
                return true;
            }
        }
    }
    /// The document's recovery: what statements left (a stray '}') is skipped statement by statement.
    bool recover_document() {
        while (la(0) != tk::end_of_text) {
            report(pos_);  // nothing while the statement's error is already reported
            skip();
            if (la(0) != tk::end_of_text) {
                r_statements();
            }
        }
        return true;
    }
    /// A block's recovery: read on to its '}'; at the end of the text the block stays unclosed (E2003).
    bool recover_block() {
        if (la(0) == tk::end_of_text) {
            return false;
        }
        while (la(0) != tk::end_of_text && la(0) != tk::RBRACE) {
            report(pos_);
            skip();
            if (la(0) != tk::end_of_text && la(0) != tk::RBRACE) {
                r_statements();
            }
        }
        return match(tk::RBRACE);
    }

private:
    void attach(raw_node done) {
        if (open_.empty()) {
            root_ = std::move(done);
        } else {
            open_.back().children.push_back(std::move(done));
        }
    }

    /// A statement's first error only: later ones are silent until a token is matched or recovery ends it.
    void report(std::size_t at) {
        if (in_error_) {
            return;
        }
        in_error_ = true;
        const level& here = levels_.back();
        const std::size_t start = here.open_directive != npos ? here.open_directive : pos_;
        const ::villanelle::diagnostic_code code = classify(tokens_, at, start, levels_.size() > 1);
        const std::string what = at < tokens_.size()
                                     ? quoted(text_.substr(tokens_[at].start, tokens_[at].end - tokens_[at].start))
                                     : std::string("end of input");
        diagnostics_.push_back({code, at, ::villanelle::describe(code, what).message});
    }

    /// Spec 3.2: skip to the end of the bad statement, its ';' outside brackets and braces or a whole block it
    /// opened; stop before the '}' closing the enclosing block; at the top level a stray '}' is consumed and ends
    /// it. The skipped tokens (and a dropped directive's) become one error node.
    void skip() {
        level& here = levels_.back();
        const std::size_t start = here.failed != npos ? here.failed : pos_;
        const std::size_t error_start = (here.failed != npos && here.discarded) ? here.failed : pos_;
        here.failed = npos;
        const bool in_block = levels_.size() > 1;
        int brackets = 0;
        int braces = 0;
        for (std::size_t i = start; i < pos_; ++i) {
            const tk kind = tokens_[i].kind;
            if (kind == tk::LBRACK) {
                ++brackets;
            } else if (kind == tk::RBRACK) {
                brackets = brackets > 0 ? brackets - 1 : 0;
            } else if (kind == tk::LBRACE) {
                ++braces;
            } else if (kind == tk::RBRACE && braces > 0) {
                --braces;
            }
        }
        for (;;) {
            const tk kind = la(0);
            if (kind == tk::end_of_text) {
                break;
            }
            if (kind == tk::RBRACE && braces == 0) {
                if (!in_block) {
                    ++pos_;
                    in_error_ = false;
                }
                break;
            }
            ++pos_;
            if (kind == tk::LBRACK) {
                ++brackets;
            } else if (kind == tk::RBRACK) {
                brackets = brackets > 0 ? brackets - 1 : 0;
            } else if (kind == tk::LBRACE) {
                ++braces;
            } else if (kind == tk::RBRACE) {
                --braces;
            }
            if ((kind == tk::RBRACE && braces == 0 && brackets == 0) ||
                (kind == tk::SEMI && brackets == 0 && braces == 0)) {
                in_error_ = false;
                break;
            }
        }
        if (pos_ > error_start) {
            attach({::villanelle::node_kind::error, error_start, pos_, {}});
        }
    }

    std::string_view text_;
    const std::vector<raw_token>& tokens_;
    std::size_t pos_ = 0;
    bool in_error_ = false;  // the current statement's error is reported
    std::vector<raw_node> open_;
    std::vector<level> levels_{level{}};
    std::vector<raw_diagnostic> diagnostics_;
    raw_node root_{::villanelle::node_kind::document, 0, 0, {}};
};

}  // namespace syntax::detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_SYNTAX_PARSE_HPP
