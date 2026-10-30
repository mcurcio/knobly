// A directive's anatomy (ts/src/anatomy.ts), a statement's text-alone shape (ts/src/written/shape.ts) and the name
// checks (ts/src/written/names.ts): the one home of each rule in this binding. The document classifies its statements
// with them, the edit checks use them, and the binding's walk reports the same codes at the same places.
#ifndef KNOBLY_DETAIL_WRITTEN_SHAPE_HPP
#define KNOBLY_DETAIL_WRITTEN_SHAPE_HPP

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <vector>

#include <knobly/detail/raise.hpp>
#include <knobly/detail/shared/values.hpp>
#include <knobly/detail/written/core.hpp>
#include <knobly/detail/written/entry.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace written::detail {

using ::knobly::token_kind;

/// WORD, AT_WORD, INTEGER or DIGIT_WORD: a word value.
inline bool is_word_kind(token_kind kind) noexcept {
    return kind == token_kind::WORD || kind == token_kind::AT_WORD || kind == token_kind::INTEGER ||
           kind == token_kind::DIGIT_WORD;
}

/// The language statement a keyword (an @word without its @) names: set, snippet or use.
inline std::optional<::knobly::statement_kind> statement_of_keyword(std::string_view word) noexcept {
    if (word == "set") {
        return ::knobly::statement_kind::set;
    }
    if (word == "snippet") {
        return ::knobly::statement_kind::snippet;
    }
    if (word == "use") {
        return ::knobly::statement_kind::use;
    }
    return std::nullopt;
}

/// The value references and the block child of a node, from token `from`: each word, STRING or VARIABLE token no
/// child covers, and each slice or list child, in source order.
inline anatomy split(const parsed_text& text, const ::knobly::syntax::node& n, std::int64_t from) {
    anatomy out;
    const ::knobly::sequence<::knobly::syntax::node> children = n.children();
    std::size_t next = 0;
    for (std::int64_t i = from; i < n.end();) {
        if (next < children.size()) {
            const ::knobly::syntax::node child = children.at(next);
            if (child.start() == i) {
                if (child.kind() == ::knobly::node_kind::slice || child.kind() == ::knobly::node_kind::list) {
                    out.values.push_back(value_ref::of(child));
                } else if (child.kind() == ::knobly::node_kind::block) {
                    out.block = child;
                }
                ++next;
                i = std::max(child.end(), i + 1);
                continue;
            }
        }
        if (text.has(i)) {
            const token_kind kind = text.at(i).kind;
            if (is_word_kind(kind) || kind == token_kind::STRING || kind == token_kind::VARIABLE) {
                out.values.push_back(value_ref::token(i));
            }
        }
        ++i;
    }
    return out;
}

/// A directive node's name token, values and block.
inline anatomy anatomy_of(const parsed_text& text, const ::knobly::syntax::node& n) {
    anatomy out = split(text, n, n.start() + 1);
    out.name = n.start();
    return out;
}

/// A list node's items, by the same rule (the bracket comes first).
inline std::vector<value_ref> items_of(const parsed_text& text, const ::knobly::syntax::node& list) {
    return split(text, list, list.start() + 1).values;
}

/// The values of a text parsed with an entry rule, from its first token.
inline std::vector<value_ref> values_of(const parsed_text& text) {
    const ::knobly::syntax::node root = text.syntax.root();
    return split(text, root, root.start()).values;
}

/// The statement nodes of a document or block node: its directive and error children.
inline std::vector<::knobly::syntax::node> statement_nodes(const ::knobly::syntax::node& container) {
    std::vector<::knobly::syntax::node> out;
    for (const ::knobly::syntax::node& child : container.children()) {
        if (child.kind() == ::knobly::node_kind::directive || child.kind() == ::knobly::node_kind::error) {
            out.push_back(child);
        }
    }
    return out;
}

/// One problem of a line's text alone.
struct shape_fault {
    ::knobly::diagnostic_code code;
    ::knobly::source_span span;
    std::string detail;  // the message detail ($a, a snippet name), if any
    bool has_detail = false;
};

/// What a directive or error node is, by its text alone.
struct shape {
    ::knobly::statement_kind kind = ::knobly::statement_kind::unreadable;
    std::optional<shape_fault> fault;
    std::optional<std::string> claims;  // a set's variable name, or a snippet's name
};

/// The shape of a directive by its anatomy, ignoring the one-per-block rules. The head's token kind decides (spec
/// 2.5): a WORD is a directive; an AT_WORD is @set, @snippet, @use, an extension line, or else unreadable (E3008).
inline shape shape_of_anatomy(const parsed_text& text, const anatomy& a, const std::set<std::string>& extensions) {
    const token_info& name = text.at(a.name);
    if (name.kind != token_kind::AT_WORD) {
        return {::knobly::statement_kind::directive, std::nullopt, std::nullopt};
    }
    const std::string_view keyword = text.text_at(a.name).substr(1);
    const value_ref* first = a.values.empty() ? nullptr : &a.values.front();
    const token_info* first_token = first != nullptr && first->is_token() ? &text.at(first->start) : nullptr;
    const auto rest = [&] { return a.values.size() > 0 ? a.values.size() - 1 : 0; };
    const std::optional<::knobly::statement_kind> statement = statement_of_keyword(keyword);
    if (statement == ::knobly::statement_kind::set) {
        if (first_token == nullptr || first_token->kind != token_kind::VARIABLE || rest() == 0 || a.block) {
            return {::knobly::statement_kind::unreadable,
                    shape_fault{::knobly::diagnostic_code::bad_set, name.span, {}, false}, std::nullopt};
        }
        return {::knobly::statement_kind::set, std::nullopt, std::string(text.text_at(first->start).substr(1))};
    }
    if (statement == ::knobly::statement_kind::snippet) {
        const shape bad{::knobly::statement_kind::unreadable,
                        shape_fault{::knobly::diagnostic_code::bad_snippet, name.span, {}, false}, std::nullopt};
        std::vector<std::string_view> params;
        for (std::size_t i = 1; i < a.values.size(); ++i) {
            const value_ref& ref = a.values[i];
            if (!ref.is_token() || text.at(ref.start).kind != token_kind::VARIABLE) {
                return bad;
            }
            const std::string_view param = text.text_at(ref.start).substr(1);
            if (std::find(params.begin(), params.end(), param) != params.end()) {
                return bad;
            }
            params.push_back(param);
        }
        if (first_token == nullptr || !is_word_kind(first_token->kind) || !a.block) {
            return bad;
        }
        return {::knobly::statement_kind::snippet, std::nullopt, std::string(text.text_at(first->start))};
    }
    if (statement == ::knobly::statement_kind::use) {
        if (first_token == nullptr || !is_word_kind(first_token->kind) || a.block) {
            return {::knobly::statement_kind::unreadable,
                    shape_fault{::knobly::diagnostic_code::bad_use, name.span, {}, false}, std::nullopt};
        }
        return {::knobly::statement_kind::use, std::nullopt, std::nullopt};
    }
    if (extensions.count(std::string(keyword)) != 0) {
        return {::knobly::statement_kind::extension, std::nullopt, std::nullopt};
    }
    return {
        ::knobly::statement_kind::unreadable,
        shape_fault{::knobly::diagnostic_code::unknown_extension, name.span, std::string(text.text_at(a.name)), true},
        std::nullopt};
}

/// The shape of one node of a block, ignoring the one-per-block rules.
inline shape shape_of(const parsed_text& text, const ::knobly::syntax::node& n,
                      const std::set<std::string>& extensions) {
    if (n.kind() != ::knobly::node_kind::directive) {
        return {};
    }
    return shape_of_anatomy(text, anatomy_of(text, n), extensions);
}

/// Whether a fault is one of the text-alone rules an edit refuses (E5002, E5005, E5009 to E5011; spec 2.8).
inline bool is_text_alone(const shape_fault& fault) noexcept {
    return fault.code != ::knobly::diagnostic_code::unknown_extension;
}

/// A snippet line's parameter tokens, in order. Call only on a well-formed snippet.
inline std::vector<std::int64_t> parameter_tokens(const parsed_text& text, const ::knobly::syntax::node& n) {
    const anatomy a = anatomy_of(text, n);
    std::vector<std::int64_t> out;
    for (std::size_t i = 1; i < a.values.size(); ++i) {
        if (a.values[i].is_token()) {
            out.push_back(a.values[i].start);
        }
    }
    return out;
}

/// The shapes of a block's nodes in order, with the one-per-block rules applied: a second set of a name is
/// unreadable (E5002 at its $name), a second snippet of a name too (E5005 at its name). `claimed` holds names the
/// block already binds (a snippet body's parameters).
inline std::vector<shape> block_shapes(const parsed_text& text, const std::vector<::knobly::syntax::node>& nodes,
                                       const std::set<std::string>& extensions,
                                       const std::vector<std::string>& claimed) {
    std::set<std::string> sets(claimed.begin(), claimed.end());
    std::set<std::string> snippets;
    std::vector<shape> out;
    out.reserve(nodes.size());
    for (const ::knobly::syntax::node& n : nodes) {
        shape s = shape_of(text, n, extensions);
        if (s.kind == ::knobly::statement_kind::set && s.claims) {
            if (sets.count(*s.claims) != 0) {
                const std::int64_t at = anatomy_of(text, n).values.front().start;
                out.push_back({::knobly::statement_kind::unreadable,
                               shape_fault{::knobly::diagnostic_code::variable_set_twice, text.at(at).span,
                                           std::string(text.text_at(at)), true},
                               std::nullopt});
                continue;
            }
            sets.insert(*s.claims);
        }
        if (s.kind == ::knobly::statement_kind::snippet && s.claims) {
            if (snippets.count(*s.claims) != 0) {
                const std::int64_t at = anatomy_of(text, n).values.front().start;
                out.push_back(
                    {::knobly::statement_kind::unreadable,
                     shape_fault{::knobly::diagnostic_code::snippet_defined_twice, text.at(at).span, *s.claims, true},
                     std::nullopt});
                continue;
            }
            snippets.insert(*s.claims);
        }
        out.push_back(std::move(s));
    }
    return out;
}

// ---- the name checks (spec 2.8, kno-umh.7): every bad name a program passes is a misuse error

/// A variable or override name, without $: load's override names, set_override and a variable's rename.
inline void check_variable_name(std::string_view name) {
    if (!::knobly::written::is_variable_name(name)) {
        ::knobly::detail::raise(::knobly::misuse_error("not a variable name (letters, digits and _): " +
                                                       ::knobly::detail::quoted_for_message(name)));
    }
}

/// A directive's new name (rename), or an extension's directive: what the nameText entry rule takes, and nothing
/// else (no directive name is reserved, spec 2.5).
inline void check_directive_name(std::string_view name) {
    if (!parse_entry(name, entry_rule::name_text).syntax.diagnostics().empty()) {
        ::knobly::detail::raise(
            ::knobly::misuse_error("not a directive name: " + ::knobly::detail::quoted_for_message(name)));
    }
}

}  // namespace written::detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_SHAPE_HPP
