// One file as written (ts/src/written/document.ts): its text, its saved text, its parse and the tree of handles over
// it. Every edit computes the new text, checks it (spec 2.8), and only then re-parses the whole document and
// reconciles the handles (spec 6.1), so a refused edit changes nothing (the strong guarantee, frozen-m2.md 3.3 rule 4).
// Package-internal.
#ifndef KNOBLY_DETAIL_WRITTEN_EDITS_HPP
#define KNOBLY_DETAIL_WRITTEN_EDITS_HPP

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

#include <knobly/detail/raise.hpp>
#include <knobly/detail/text_in.hpp>
#include <knobly/detail/written/core.hpp>
#include <knobly/detail/written/entry.hpp>
#include <knobly/detail/written/shape.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace written::detail {

// ---- text helpers with JavaScript's semantics, so offsets agree with the reference binding

/// String.prototype.lastIndexOf for one character: the last index at or before `from` (clamped to the text), or -1.
inline std::int64_t last_index_of(std::string_view text, char c, std::int64_t from) noexcept {
    if (text.empty()) {
        return -1;
    }
    std::int64_t at =
        std::min<std::int64_t>(std::max<std::int64_t>(from, 0), static_cast<std::int64_t>(text.size()) - 1);
    for (; at >= 0; --at) {
        if (text[static_cast<std::size_t>(at)] == c) {
            return at;
        }
    }
    return -1;
}

/// String.prototype.indexOf for one character, from `from`; -1 when absent.
inline std::int64_t index_of(std::string_view text, char c, std::int64_t from) noexcept {
    const std::size_t found = text.find(c, static_cast<std::size_t>(std::max<std::int64_t>(from, 0)));
    return found == std::string_view::npos ? -1 : static_cast<std::int64_t>(found);
}

/// String.prototype.slice for non-negative bounds: empty when start is at or after end.
inline std::string_view slice(std::string_view text, std::int64_t start, std::int64_t end) noexcept {
    const auto size = static_cast<std::int64_t>(text.size());
    start = std::clamp<std::int64_t>(start, 0, size);
    end = std::clamp<std::int64_t>(end, 0, size);
    return start >= end ? std::string_view()
                        : text.substr(static_cast<std::size_t>(start), static_cast<std::size_t>(end - start));
}

inline constexpr std::string_view bom = "\xEF\xBB\xBF";

/// Whether text holds only spaces and tabs (and byte-order marks, when `marks`).
inline bool only_blanks(std::string_view text, bool marks) noexcept {
    for (std::size_t i = 0; i < text.size();) {
        if (text[i] == ' ' || text[i] == '\t') {
            ++i;
        } else if (marks && text.substr(i, bom.size()) == bom) {
            i += bom.size();
        } else {
            return false;
        }
    }
    return true;
}

/// The grammar's spaces and line breaks only (space, tab, CR, LF): what an edit given it removes or inserts nothing
/// for. Not a Unicode trim, which would also take U+FEFF and other spaces the grammar refuses.
inline bool is_blank(std::string_view text) noexcept {
    return std::all_of(text.begin(), text.end(),
                       [](char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; });
}

/// JavaScript's \s: the code points String.prototype.trim removes.
inline bool is_js_space(char32_t cp) noexcept {
    return (cp >= 0x09 && cp <= 0x0D) || cp == 0x20 || cp == 0xA0 || cp == 0x1680 || (cp >= 0x2000 && cp <= 0x200A) ||
           cp == 0x2028 || cp == 0x2029 || cp == 0x202F || cp == 0x205F || cp == 0x3000 || cp == 0xFEFF;
}

/// Whether trim() of the text is empty.
inline bool trims_empty(std::string_view text) noexcept {
    for (std::size_t at = 0; at < text.size();) {
        char32_t cp = 0;
        const std::size_t length = ::knobly::detail::decode_utf8(text, at, cp);
        if (length == 0 || !is_js_space(cp)) {
            return false;
        }
        at += length;
    }
    return true;
}

/// The leading run of spaces and tabs.
inline std::string_view leading_blanks(std::string_view text) noexcept {
    std::size_t at = 0;
    while (at < text.size() && (text[at] == ' ' || text[at] == '\t')) {
        ++at;
    }
    return text.substr(0, at);
}

/// The position of `offset` in `text`: line and column from 0, in bytes.
inline ::knobly::source_position position_in(std::string_view text, std::int64_t offset) noexcept {
    const std::int64_t at = std::clamp<std::int64_t>(offset, 0, static_cast<std::int64_t>(text.size()));
    std::int64_t line = 0;
    std::int64_t line_start = 0;
    for (std::int64_t i = 0; i < at; ++i) {
        if (text[static_cast<std::size_t>(i)] == '\n') {
            ++line;
            line_start = i + 1;
        }
    }
    return {at, line, at - line_start};
}

/// A zero-width diagnostic of `code` at `offset` of the text an edit was given.
inline ::knobly::diagnostic diagnostic_at(std::string_view given, std::int64_t offset, ::knobly::diagnostic_code code) {
    const ::knobly::source_position position = position_in(given, offset);
    return {code, ::knobly::describe(code).message, {position, position}};
}

// ---- what an edit splices in

/// A piece of an insert: text the edit adds, or the range [from, to) of the caller's text it copies.
using piece = std::variant<std::string, std::pair<std::int64_t, std::int64_t>>;

/// What an edit splices in: its text, the caller's text, and for each byte its offset there (-1: added), so a problem
/// in what the caller gave is located in the caller's text (spec 2.8).
struct insert {
    std::string text;
    std::string given;
    std::vector<std::int64_t> origin;
};

inline insert insert_of(std::string_view given, const std::vector<piece>& pieces) {
    insert out{{}, std::string(given), {}};
    for (const piece& p : pieces) {
        if (const auto* added = std::get_if<std::string>(&p)) {
            out.text += *added;
            out.origin.insert(out.origin.end(), added->size(), -1);
        } else {
            const auto [from, to] = std::get<std::pair<std::int64_t, std::int64_t>>(p);
            out.text += slice(given, from, to);
            for (std::int64_t i = from; i < to; ++i) {
                out.origin.push_back(i);
            }
        }
    }
    return out;
}

/// The caller's text whole.
inline insert insert_of(std::string_view given) {
    return insert_of(given, {std::pair<std::int64_t, std::int64_t>(0, static_cast<std::int64_t>(given.size()))});
}

// ---- token ranges of the current parse

inline bool is_trivia(::knobly::token_kind kind) noexcept {
    return kind == ::knobly::token_kind::SPACE || kind == ::knobly::token_kind::NEWLINE;
}

using token_span = std::pair<std::int64_t, std::int64_t>;  // a token range [start, end)

/// A statement's owned token range (spec 6.4): from a comment line directly above it to its trailing comment.
inline token_span owned_range(const parsed_text& p, const ::knobly::syntax::node& n) {
    using ::knobly::token_kind;
    std::int64_t first = n.start();
    std::int64_t last = n.end() - 1;
    while (last > first && p.has(last) && is_trivia(p.at(last).kind)) {
        --last;
    }
    std::int64_t j = last + 1;
    while (p.is(j, token_kind::SPACE)) {
        ++j;
    }
    if (p.is(j, token_kind::COMMENT)) {
        last = j;
    }
    // Comment lines directly above, only when the statement starts its line.
    std::int64_t k = first - 1;
    while (p.is(k, token_kind::SPACE)) {
        --k;
    }
    if (k < 0 || p.is(k, token_kind::NEWLINE) || p.is(k, token_kind::BOM)) {
        for (;;) {
            if (!p.is(k, token_kind::NEWLINE)) {
                break;
            }
            std::int64_t m = k - 1;
            while (p.is(m, token_kind::SPACE)) {
                --m;
            }
            if (!p.is(m, token_kind::COMMENT)) {
                break;
            }
            const std::int64_t comment = m;
            --m;
            while (p.is(m, token_kind::SPACE)) {
                --m;
            }
            if (!(m < 0 || p.is(m, token_kind::NEWLINE) || p.is(m, token_kind::BOM))) {
                break;
            }
            first = comment;
            k = m;
        }
    }
    return {first, last + 1};
}

/// A node's range without trailing spaces and line breaks.
inline token_span trimmed(const parsed_text& p, const ::knobly::syntax::node& n) {
    std::int64_t end = n.end();
    while (end > n.start() + 1 && p.has(end - 1) && is_trivia(p.at(end - 1).kind)) {
        --end;
    }
    return {n.start(), end};
}

inline std::pair<std::int64_t, std::int64_t> offsets_of(const parsed_text& p, token_span range) {
    const auto [from, to] = p.offsets(range.first, range.second);
    return {static_cast<std::int64_t>(from), static_cast<std::int64_t>(to)};
}

/// The values inside a value, in text order: a list's items, a slice's or index's name and bounds.
inline std::vector<value_node*> inner_handles(const value_node* v) {
    switch (v->kind) {
        case ::knobly::value_kind::list:
            return v->items;
        case ::knobly::value_kind::slice: {
            std::vector<value_node*> out;
            for (value_node* inner : {v->name, v->start, v->end}) {
                if (inner != nullptr) {
                    out.push_back(inner);
                }
            }
            return out;
        }
        case ::knobly::value_kind::index: {
            std::vector<value_node*> out;
            for (value_node* inner : {v->name, v->index}) {
                if (inner != nullptr) {
                    out.push_back(inner);
                }
            }
            return out;
        }
        default:
            return {};
    }
}

// ---- the reconcile (spec 6.1)

/// A handle's old token range, in offsets of the text before an edit.
struct old_entry {
    handle_node* handle;
    std::int64_t start;
    std::int64_t end;
};

/// The replaced range in old offsets, and the length of what replaced it.
struct edit_range {
    std::int64_t start;
    std::int64_t end;
    std::int64_t inserted;
};

/// Matches the handles of a new parse to the old ones (document.ts Reconcile).
class reconcile {
public:
    std::vector<handle_node*> created;

    reconcile(std::map<std::string, old_entry> old, std::optional<edit_range> range, handle_node* keep = nullptr)
        : old_(std::move(old)), range_(range), keep_(keep) {}

    /// The old handle of `key` that the new parse's handle starting at new_start continues, or null.
    handle_node* take(const std::string& key, std::int64_t new_start) {
        if (!range_) {
            return nullptr;
        }
        const edit_range& range = *range_;
        const std::int64_t delta = range.inserted - (range.end - range.start);
        std::int64_t old_start = 0;
        if (new_start < range.start) {
            old_start = new_start;
        } else if (new_start >= range.start + range.inserted) {
            old_start = new_start - delta;
        } else if (new_start == range.start) {
            return at_start(key);
        } else {
            return kept_inside(key);
        }
        const auto found = old_.find(key + "@" + std::to_string(old_start));
        if (found == old_.end()) {
            return nullptr;
        }
        const old_entry& entry = found->second;
        const bool outside = entry.end <= range.start || entry.start >= range.end;
        const bool contains = entry.start <= range.start && entry.end >= range.end &&
                              (entry.start < range.start || entry.end > range.end);
        if (!outside && !contains) {
            return nullptr;
        }
        handle_node* const handle = entry.handle;
        old_.erase(found);
        return handle;
    }

    /// Handles left over: their tokens were replaced.
    std::vector<handle_node*> leftovers() const {
        std::vector<handle_node*> out;
        out.reserve(old_.size());
        for (const auto& [id, entry] : old_) {
            out.push_back(entry.handle);
        }
        return out;
    }

private:
    static char family_of(const std::string& key) noexcept { return key.empty() ? '\0' : key.front(); }

    /// A handle starting where the replaced range starts: an old one of the same key whose tokens hold the range and
    /// more, else the one the edit keeps, of its family whatever its kind, else none.
    handle_node* at_start(const std::string& key) {
        const edit_range& range = *range_;
        const auto found = old_.find(key + "@" + std::to_string(range.start));
        if (found != old_.end() && found->second.handle != keep_ && range.end > range.start &&
            found->second.end > range.end) {
            handle_node* const handle = found->second.handle;
            old_.erase(found);
            return handle;
        }
        if (keep_ == nullptr) {
            return nullptr;
        }
        for (auto it = old_.begin(); it != old_.end(); ++it) {
            if (it->second.handle != keep_) {
                continue;
            }
            if (family_of(it->first) != family_of(key) || it->second.start != range.start) {
                return nullptr;
            }
            old_.erase(it);
            return keep_;
        }
        return nullptr;
    }

    /// A value built inside what replaced the range but not at its start: the value the edit keeps.
    handle_node* kept_inside(const std::string& key) {
        if (keep_ == nullptr || family_of(key) != 'v') {
            return nullptr;
        }
        for (auto it = old_.begin(); it != old_.end(); ++it) {
            if (it->second.handle != keep_) {
                continue;
            }
            if (family_of(it->first) != 'v') {
                return nullptr;
            }
            old_.erase(it);
            return keep_;
        }
        return nullptr;
    }

    std::map<std::string, old_entry> old_;
    std::optional<edit_range> range_;
    handle_node* keep_;
};

// ---- building the handle tree

inline std::string statement_key(::knobly::statement_kind kind) { return "s:" + std::string(to_string(kind)); }
inline std::string value_key(::knobly::value_kind kind) { return "v:" + std::string(to_string(kind)); }

/// The handles currently in a document's tree, by reconcile key (document.ts entries).
inline std::map<std::string, old_entry> entries_of(const document_node* doc) {
    std::map<std::string, old_entry> out;
    const parsed_text& p = doc->parsed;
    const auto add = [&](const std::string& key, handle_node* handle, token_span range) {
        const auto [start, end] = offsets_of(p, range);
        out.insert_or_assign(key + "@" + std::to_string(start), old_entry{handle, start, end});
    };
    std::function<void(value_node*)> value = [&](value_node* v) {
        add(value_key(v->kind), v, {v->ref.start, v->ref.end});
        for (value_node* inner : inner_handles(v)) {
            value(inner);
        }
    };
    std::function<void(statement_node*)> statement = [&](statement_node* s) {
        add(statement_key(s->kind), s, trimmed(p, s->tree));
        for (value_node* v : s->values) {
            value(v);
        }
        if (s->kind == ::knobly::statement_kind::snippet) {
            for (variable_node* param : s->parameters) {
                add("p", param, {param->token, param->token + 1});
            }
        }
        if (s->block != nullptr) {
            for (statement_node* child : s->block->handles) {
                statement(child);
            }
        }
    };
    for (statement_node* s : doc->block->handles) {
        statement(s);
    }
    return out;
}

/// A written value's kind by its tokens.
inline ::knobly::value_kind value_kind_of(const parsed_text& p, const value_ref& ref) {
    if (!ref.is_token()) {
        if (ref.tree->kind() == ::knobly::node_kind::list) {
            return ::knobly::value_kind::list;
        }
        for (std::int64_t i = ref.start + 2; i < ref.end - 1; ++i) {
            if (p.is(i, ::knobly::token_kind::TILDE)) {
                return ::knobly::value_kind::slice;
            }
        }
        return ref.end - ref.start > 3 ? ::knobly::value_kind::index : ::knobly::value_kind::slice;
    }
    if (p.is(ref.start, ::knobly::token_kind::STRING)) {
        return ::knobly::value_kind::string;
    }
    if (p.is(ref.start, ::knobly::token_kind::VARIABLE)) {
        return ::knobly::value_kind::reference;
    }
    return ::knobly::value_kind::word;
}

/// Builds a document's handle tree over its current parse (document.ts build).
class builder {
public:
    builder(document_node* doc, reconcile& r) : doc_(doc), p_(doc->parsed), reconcile_(r) {}

    void build() {
        doc_->statements_by_token.clear();
        doc_->values_by_token.clear();
        doc_->block->handles = block(p_.syntax.root(), nullptr, {});
    }

private:
    std::vector<statement_node*> block(const ::knobly::syntax::node& container, statement_node* owner,
                                       const std::vector<std::string>& claimed) {
        const std::vector<::knobly::syntax::node> nodes = statement_nodes(container);
        const std::vector<shape> shapes = block_shapes(p_, nodes, doc_->graph->extension_names, claimed);
        std::vector<statement_node*> out;
        out.reserve(nodes.size());
        for (std::size_t i = 0; i < nodes.size(); ++i) {
            out.push_back(statement(nodes[i], shapes[i], owner));
        }
        return out;
    }

    statement_node* make_statement(::knobly::statement_kind kind) {
        statement_node* made = doc_->graph->nodes.make<statement_node>(kind, doc_);
        if (kind == ::knobly::statement_kind::set) {
            made->variable = doc_->graph->nodes.make<variable_node>(::knobly::variable_kind::set);
            made->variable->line = made;
        }
        return made;
    }

    statement_node* statement(const ::knobly::syntax::node& n, const shape& s, statement_node* owner) {
        handle_node* const kept =
            reconcile_.take(statement_key(s.kind), static_cast<std::int64_t>(p_.start_of(n.start())));
        statement_node* const handle =
            kept != nullptr && kept->family == 's' ? static_cast<statement_node*>(kept) : make_statement(s.kind);
        if (kept == nullptr) {
            reconcile_.created.push_back(handle);
        }
        handle->tree = n;
        handle->parent = owner;
        handle->detached = false;
        doc_->statements_by_token[n.start()] = handle;
        std::optional<anatomy> a;
        if (n.kind() == ::knobly::node_kind::directive) {
            a = anatomy_of(p_, n);
        }
        const auto values = [&](std::size_t skip) {
            std::vector<value_node*> out;
            if (a) {
                for (std::size_t i = skip; i < a->values.size(); ++i) {
                    out.push_back(value(a->values[i], handle, nullptr, value_role::value));
                }
            }
            return out;
        };
        const auto inner_block = [&](const std::vector<std::string>& claimed) {
            if (!a || !a->block) {
                handle->block = nullptr;
                return;
            }
            if (handle->block == nullptr) {
                handle->block = doc_->graph->nodes.make<block_node>();
                handle->block->doc = doc_;
                handle->block->owner = handle;
            }
            handle->block->handles = block(*a->block, handle, claimed);
        };
        switch (handle->kind) {
            case ::knobly::statement_kind::directive:
            case ::knobly::statement_kind::extension:
                handle->values = values(0);
                inner_block({});
                break;
            case ::knobly::statement_kind::set:
            case ::knobly::statement_kind::use:
                handle->values = values(1);
                handle->block = nullptr;
                break;
            case ::knobly::statement_kind::snippet: {
                handle->values.clear();
                handle->parameters.clear();
                std::vector<std::string> names;
                for (const std::int64_t token : parameter_tokens(p_, n)) {
                    handle_node* const kept_parameter =
                        reconcile_.take("p", static_cast<std::int64_t>(p_.start_of(token)));
                    variable_node* parameter = nullptr;
                    if (kept_parameter != nullptr && kept_parameter->family == 'p') {
                        parameter = static_cast<variable_node*>(kept_parameter);
                    } else {
                        parameter = doc_->graph->nodes.make<variable_node>(::knobly::variable_kind::parameter);
                        parameter->line = handle;
                    }
                    if (kept_parameter == nullptr) {
                        reconcile_.created.push_back(parameter);
                    }
                    parameter->token = token;
                    parameter->detached = false;
                    handle->parameters.push_back(parameter);
                    names.emplace_back(p_.text_at(token).substr(1));
                }
                inner_block(names);
                break;
            }
            case ::knobly::statement_kind::unreadable:
                handle->values.clear();
                handle->block = nullptr;
                break;
        }
        return handle;
    }

    value_node* value(const value_ref& ref, statement_node* statement, value_node* list, value_role role) {
        const ::knobly::value_kind kind = value_kind_of(p_, ref);
        handle_node* const kept = reconcile_.take(value_key(kind), static_cast<std::int64_t>(p_.start_of(ref.start)));
        value_node* const handle = kept != nullptr && kept->family == 'v'
                                       ? static_cast<value_node*>(kept)
                                       : doc_->graph->nodes.make<value_node>(kind, doc_);
        if (kept == nullptr) {
            reconcile_.created.push_back(handle);
        }
        if (handle->kind != kind) {
            // A kept handle takes the new value's kind (spec 6.1), with no inner handles until they are built.
            handle->kind = kind;
            handle->items.clear();
            handle->name = handle->start = handle->end = handle->index = nullptr;
        }
        handle->ref = ref;
        handle->statement = statement;
        handle->list = list;
        handle->role = role;
        handle->detached = false;
        // A slice and its name start at the same token: the index keeps the slice (its name is slice.name).
        if (role != value_role::name) {
            doc_->values_by_token[ref.start] = handle;
        }
        if (kind == ::knobly::value_kind::list && !ref.is_token()) {
            std::vector<value_node*> items;
            for (const value_ref& item : items_of(p_, *ref.tree)) {
                items.push_back(value(item, statement, handle, value_role::value));
            }
            handle->items = std::move(items);
        } else if ((kind == ::knobly::value_kind::slice || kind == ::knobly::value_kind::index) && !ref.is_token()) {
            handle->name = value(value_ref::token(ref.start), statement, nullptr, value_role::name);
            std::vector<std::int64_t> inner;
            for (std::int64_t i = ref.start + 2; i < ref.end - 1; ++i) {
                inner.push_back(i);
            }
            std::int64_t tilde = -1;
            for (std::size_t i = 0; i < inner.size(); ++i) {
                if (p_.is(inner[i], ::knobly::token_kind::TILDE)) {
                    tilde = static_cast<std::int64_t>(i);
                    break;
                }
            }
            const auto bound_at = [&](std::int64_t at) -> value_node* {
                if (at < 0 || at >= static_cast<std::int64_t>(inner.size())) {
                    return nullptr;
                }
                const std::int64_t token = inner[static_cast<std::size_t>(at)];
                if (p_.is(token, ::knobly::token_kind::INTEGER) || p_.is(token, ::knobly::token_kind::VARIABLE)) {
                    return value(value_ref::token(token), statement, nullptr, value_role::bound);
                }
                return nullptr;
            };
            if (kind == ::knobly::value_kind::index) {
                handle->index = bound_at(0);
            } else {
                handle->start = tilde == 0 ? nullptr : bound_at(0);
                handle->end = tilde + 1 < static_cast<std::int64_t>(inner.size()) ? bound_at(tilde + 1) : nullptr;
            }
        }
        return handle;
    }

    document_node* doc_;
    const parsed_text& p_;
    reconcile& reconcile_;
};

/// A new document over its text, its handles built (document.ts constructor).
inline document_node* make_document(graph_core* graph, std::string resolved_path, std::string text) {
    document_node* doc =
        graph->nodes.make<document_node>(graph, std::move(resolved_path), parse_document(std::move(text)));
    doc->block = graph->nodes.make<block_node>();
    doc->block->doc = doc;
    reconcile none({}, std::nullopt);
    builder(doc, none).build();
    return doc;
}

/// Re-parses a document's new text and reconciles its handles; leftovers are detached; the graph is told first, so
/// a build that fails part way (std::bad_alloc) never leaves the cached binding in use over the new parse.
inline std::vector<handle_node*> adopt(document_node* doc, parsed_text parsed, reconcile r) {
    ++doc->graph->version;
    doc->parsed = std::move(parsed);
    builder(doc, r).build();
    for (handle_node* left : r.leftovers()) {
        left->detached = true;
    }
    return std::move(r.created);
}

/// replace_with_text of a document: the text whole, unchecked; every handle is new.
inline void replace_document(document_node* doc, std::string_view text) {
    reconcile none(entries_of(doc), std::nullopt);
    adopt(doc, parse_document(std::string(text)), std::move(none));
}

// ---- the text-alone rules an edit refuses (E5002, E5005, E5009 to E5011)

/// The text-alone rules a spliced text would break, on the statements the splice touches: located in the caller's
/// text when the problem lies in what it gave (spec 2.8), else at 0:0.
inline std::vector<::knobly::diagnostic> rule_problems(const parsed_text& p, const std::set<std::string>& extensions,
                                                       std::int64_t from, const insert& ins) {
    std::vector<::knobly::diagnostic> out;
    const std::int64_t to = from + static_cast<std::int64_t>(ins.text.size());
    const auto overlaps = [&](std::int64_t s, std::int64_t e) {
        return from == to ? s < from && e > from : s < to && e > from;
    };
    const auto touches = [&](const ::knobly::syntax::node& n) {
        const ::knobly::source_span span = p.span_of(n.start(), n.end());
        return overlaps(span.start().offset(), span.end().offset());
    };
    const auto report = [&](const shape_fault& fault) {
        const std::int64_t offset = fault.span.start().offset();
        const std::int64_t origin =
            offset >= from && offset < to ? ins.origin[static_cast<std::size_t>(offset - from)] : -1;
        out.push_back(diagnostic_at(ins.given, std::max<std::int64_t>(origin, 0), fault.code));
    };
    std::function<void(const ::knobly::syntax::node&, const std::vector<std::string>&, const std::set<std::string>&)>
        visit = [&](const ::knobly::syntax::node& container, const std::vector<std::string>& claimed,
                    const std::set<std::string>& touched_claims) {
            const std::vector<::knobly::syntax::node> nodes = statement_nodes(container);
            const std::vector<shape> shapes = block_shapes(p, nodes, extensions, claimed);
            for (std::size_t i = 0; i < nodes.size(); ++i) {
                const ::knobly::syntax::node& n = nodes[i];
                const shape& s = shapes[i];
                if (s.fault && is_text_alone(*s.fault)) {
                    const ::knobly::diagnostic_code code = s.fault->code;
                    bool involved = touches(n);
                    if (!involved && (code == ::knobly::diagnostic_code::variable_set_twice ||
                                      code == ::knobly::diagnostic_code::snippet_defined_twice)) {
                        std::string name = s.fault->detail;
                        if (!name.empty() && name.front() == '$') {
                            name.erase(0, 1);
                        }
                        involved =
                            code == ::knobly::diagnostic_code::variable_set_twice && touched_claims.count(name) != 0;
                        for (std::size_t j = 0; j < i && !involved; ++j) {
                            involved = touches(nodes[j]) && shapes[j].claims == name;
                        }
                    }
                    if (involved) {
                        report(*s.fault);
                    }
                }
                if (n.kind() != ::knobly::node_kind::directive) {
                    continue;
                }
                const anatomy a = anatomy_of(p, n);
                if (!a.block || s.kind == ::knobly::statement_kind::unreadable) {
                    continue;
                }
                const std::vector<std::int64_t> params =
                    s.kind == ::knobly::statement_kind::snippet ? parameter_tokens(p, n) : std::vector<std::int64_t>();
                std::vector<std::string> names;
                std::set<std::string> touched;
                for (const std::int64_t t : params) {
                    const std::string name(p.text_at(t).substr(1));
                    names.push_back(name);
                    const token_info& token = p.at(t);
                    if (overlaps(static_cast<std::int64_t>(token.start), static_cast<std::int64_t>(token.end))) {
                        touched.insert(name);
                    }
                }
                visit(*a.block, names, touched);
            }
        };
    visit(p.syntax.root(), {}, {});
    return out;
}

// ---- edits (spec 6.4 to 6.7)

/// Replaces the offsets [start, end) with `ins`, after `given` (the entry rule's diagnostics, in the caller's text)
/// and the text-alone rules found nothing wrong; then re-parses, reconciles and tells the graph. Returns the handles
/// made for the inserted text. @throws bad_text_error, changing nothing
inline std::vector<handle_node*> splice(document_node* doc, std::int64_t start, std::int64_t end, const insert& ins,
                                        const std::vector<::knobly::diagnostic>& given, handle_node* keep = nullptr) {
    if (!given.empty()) {
        ::knobly::detail::raise(::knobly::bad_text_error(given));
    }
    const std::string& current = doc->parsed.text;
    std::string text(slice(current, 0, start));
    text += ins.text;
    text += slice(current, end, static_cast<std::int64_t>(current.size()));
    parsed_text parsed = parse_document(std::move(text));
    const std::vector<::knobly::diagnostic> rules = rule_problems(parsed, doc->graph->extension_names, start, ins);
    if (!rules.empty()) {
        ::knobly::detail::raise(::knobly::bad_text_error(rules));
    }
    reconcile r(entries_of(doc), edit_range{start, end, static_cast<std::int64_t>(ins.text.size())}, keep);
    return adopt(doc, std::move(parsed), std::move(r));
}

inline std::vector<::knobly::diagnostic> diagnostics_of(const parsed_text& p) {
    const ::knobly::sequence<::knobly::diagnostic> found = p.syntax.diagnostics();
    return {found.begin(), found.end()};
}

/// The line break a document uses: its first, else \n.
inline std::string line_break(const document_node* doc) {
    const std::string& text = doc->parsed.text;
    const std::size_t newline = text.find('\n');
    if (newline == std::string::npos) {
        return "\n";
    }
    return newline > 0 && text[newline - 1] == '\r' ? "\r\n" : "\n";
}

/// The leading whitespace of the line holding `offset`.
inline std::string indentation_at(const document_node* doc, std::int64_t offset) {
    const std::string& text = doc->parsed.text;
    const std::int64_t line_start = last_index_of(text, '\n', offset - 1) + 1;
    return std::string(leading_blanks(slice(text, line_start, static_cast<std::int64_t>(text.size()))));
}

/// The document's indentation unit: the leading whitespace of its first indented line, else four spaces (D14).
inline std::string indentation_unit(const document_node* doc) {
    const std::string_view text = doc->parsed.text;
    for (std::size_t line = 0; line <= text.size();) {
        const std::string_view run = leading_blanks(text.substr(line));
        const std::size_t next = line + run.size();
        if (!run.empty() && next < text.size()) {
            char32_t cp = 0;
            const std::size_t length = ::knobly::detail::decode_utf8(text, next, cp);
            if (length == 0 || !is_js_space(cp)) {
                return std::string(run);
            }
        }
        const std::size_t newline = text.find_first_of("\n\r", line);
        if (newline == std::string_view::npos) {
            break;
        }
        line = newline + 1;
    }
    return "    ";
}

/// The range a removal of [start, end) deletes: whole lines when nothing else is on them, else one space more.
inline std::pair<std::int64_t, std::int64_t> removal_range(const document_node* doc, std::int64_t start,
                                                           std::int64_t end) {
    const std::string_view text = doc->parsed.text;
    const auto size = static_cast<std::int64_t>(text.size());
    const std::int64_t line_start = last_index_of(text, '\n', start - 1) + 1;
    const std::int64_t newline = index_of(text, '\n', end);
    const std::int64_t line_end = newline < 0 ? size : newline;
    const std::string_view before = slice(text, line_start, start);
    std::string_view after = slice(text, end, line_end);
    if (!after.empty() && after.back() == '\r') {
        after.remove_suffix(1);
    }
    if (only_blanks(before, true) && only_blanks(after, false)) {
        const std::int64_t bomless =
            line_start == 0 && text.substr(0, bom.size()) == bom ? static_cast<std::int64_t>(bom.size()) : 0;
        return {line_start + bomless, newline < 0 ? size : newline + 1};
    }
    const auto blank_at = [&](std::int64_t i) {
        return i >= 0 && i < size &&
               (text[static_cast<std::size_t>(i)] == ' ' || text[static_cast<std::size_t>(i)] == '\t');
    };
    if (blank_at(end)) {
        return {start, end + 1};
    }
    if (start > 0 && blank_at(start - 1)) {
        return {start - 1, end};
    }
    return {start, end};
}

/// remove() of a statement (spec 6.4): its owned span, and its lines when nothing else is on them.
inline void remove_statement(statement_node* s) {
    document_node* doc = s->doc;
    const auto [start, end] = offsets_of(doc->parsed, owned_range(doc->parsed, s->tree));
    const auto [from, to] = removal_range(doc, start, end);
    splice(doc, from, to, insert_of(""), {});
}

/// The given statements text with its common indentation removed and later lines prefixed with `indentation`, as
/// pieces of an insert (each line keeps its place in the given text, for spec 2.8's locations).
inline std::vector<piece> reindent(const document_node* doc, std::string_view text, const std::string& indentation) {
    // Leading blank lines.
    std::size_t lead = 0;
    for (;;) {
        std::size_t k = lead;
        while (k < text.size() && (text[k] == ' ' || text[k] == '\t')) {
            ++k;
        }
        if (k + 1 < text.size() && text[k] == '\r' && text[k + 1] == '\n') {
            lead = k + 2;
        } else if (k < text.size() && text[k] == '\n') {
            lead = k + 1;
        } else {
            break;
        }
    }
    const std::string_view rest = text.substr(lead);
    // Trailing line breaks and the blanks after them.
    std::size_t body_end = rest.size();
    for (std::size_t at = rest.size();;) {
        std::size_t k = at;
        while (k > 0 && (rest[k - 1] == ' ' || rest[k - 1] == '\t')) {
            --k;
        }
        if (k > 0 && rest[k - 1] == '\n') {
            --k;
            if (k > 0 && rest[k - 1] == '\r') {
                --k;
            }
            at = k;
            body_end = k;
        } else {
            break;
        }
    }
    const std::string_view body = rest.substr(0, body_end);
    struct line {
        std::string_view text;
        std::int64_t at;
    };
    std::vector<line> lines;
    std::size_t from = 0;
    for (std::size_t i = 0; i < body.size(); ++i) {
        if (body[i] != '\n') {
            continue;
        }
        const std::size_t match = i > 0 && body[i - 1] == '\r' ? i - 1 : i;
        if (match < from) {
            continue;
        }
        lines.push_back({body.substr(from, match - from), static_cast<std::int64_t>(lead + from)});
        from = i + 1;
    }
    lines.push_back({body.substr(from), static_cast<std::int64_t>(lead + from)});
    std::int64_t common = std::numeric_limits<std::int64_t>::max();
    for (const line& l : lines) {
        if (!trims_empty(l.text)) {
            common = std::min(common, static_cast<std::int64_t>(leading_blanks(l.text).size()));
        }
    }
    const std::string eol = line_break(doc);
    std::vector<piece> pieces;
    for (std::size_t i = 0; i < lines.size(); ++i) {
        const line& l = lines[i];
        if (i > 0) {
            pieces.emplace_back(eol);
        }
        if (i > 0 && trims_empty(l.text)) {
            continue;
        }
        if (i > 0) {
            pieces.emplace_back(indentation);
        }
        const std::int64_t length = static_cast<std::int64_t>(l.text.size());
        pieces.emplace_back(std::pair<std::int64_t, std::int64_t>(l.at + std::min(common, length), l.at + length));
    }
    return pieces;
}

/// The statements among the created handles whose parent is `owner`, as their nodes.
inline std::vector<statement_node*> created_statements(const std::vector<handle_node*>& created,
                                                       statement_node* owner) {
    std::vector<statement_node*> out;
    for (handle_node* h : created) {
        if (h->family == 's' && static_cast<statement_node*>(h)->parent == owner) {
            out.push_back(static_cast<statement_node*>(h));
        }
    }
    return out;
}

/// replace_with_text of a statement: zero or more statements, indented as it is.
inline std::vector<statement_node*> replace_statement(statement_node* s, std::string_view text) {
    document_node* doc = s->doc;
    const std::vector<::knobly::diagnostic> given = diagnostics_of(parse_entry(text, entry_rule::statements_text));
    if (is_blank(text)) {
        if (!given.empty()) {
            ::knobly::detail::raise(::knobly::bad_text_error(given));
        }
        remove_statement(s);
        return {};
    }
    const auto [start, end] = offsets_of(doc->parsed, owned_range(doc->parsed, s->tree));
    const insert ins = insert_of(text, reindent(doc, text, indentation_at(doc, start)));
    statement_node* owner = s->parent;
    return created_statements(splice(doc, start, end, ins, given), owner);
}

/// insert_statements (spec 6.5): the text's lines, common indentation removed, each prefixed with the siblings'
/// indentation (in an empty block: the parent's line indentation plus the document's unit), on lines of their own
/// before handles[index] (its owned comments stay with it), or after the last statement.
inline std::vector<statement_node*> insert_statements(block_node* block, std::size_t index, std::string_view text) {
    document_node* doc = block->doc;
    const std::vector<::knobly::diagnostic> given = diagnostics_of(parse_entry(text, entry_rule::statements_text));
    if (is_blank(text)) {
        if (!given.empty()) {
            ::knobly::detail::raise(::knobly::bad_text_error(given));
        }
        return {};
    }
    const std::string eol = line_break(doc);
    const std::string& current = doc->parsed.text;
    const parsed_text& p = doc->parsed;
    const std::vector<statement_node*>& items = block->handles;
    const auto lines = [&](const std::string& indentation) {
        std::vector<piece> out{indentation};
        for (piece& each : reindent(doc, text, indentation)) {
            out.push_back(std::move(each));
        }
        return out;
    };
    const auto append = [](std::vector<piece> a, const std::vector<piece>& b) {
        a.insert(a.end(), b.begin(), b.end());
        return a;
    };
    std::int64_t at = 0;
    std::vector<piece> pieces;
    if (!items.empty()) {
        const std::string indentation = indentation_at(doc, offsets_of(p, owned_range(p, items.front()->tree)).first);
        if (index < items.size()) {
            const std::int64_t start = offsets_of(p, owned_range(p, items[index]->tree)).first;
            const std::int64_t line_start = last_index_of(current, '\n', start - 1) + 1;
            if (only_blanks(slice(current, line_start, start), true)) {
                // On lines of their own before the target's line (a BOM stays first).
                at = line_start + (line_start == 0 && current.compare(0, bom.size(), bom) == 0
                                       ? static_cast<std::int64_t>(bom.size())
                                       : 0);
                pieces = append(lines(indentation), {eol});
            } else {
                // The target shares its line with an earlier statement: the new lines go between them.
                at = start;
                pieces = append(reindent(doc, text, indentation), {eol, indentation_at(doc, start)});
            }
        } else {
            at = offsets_of(p, owned_range(p, items.back()->tree)).second;
            pieces = append({eol}, lines(indentation));
        }
    } else if (block->owner == nullptr) {
        // An empty document: at its end, on lines of their own.
        at = static_cast<std::int64_t>(current.size());
        const std::string open = current.empty() || current.back() == '\n' ? "" : eol;
        pieces = append(append({open}, lines("")), {eol});
    } else {
        const std::optional<::knobly::syntax::node> node = anatomy_of(p, block->owner->tree).block;
        const auto open = static_cast<std::int64_t>(p.at(node->start()).end);
        const auto close = static_cast<std::int64_t>(p.at(node->end() - 1).start);
        const std::string parent_indentation =
            indentation_at(doc, offsets_of(p, {block->owner->tree.start(), block->owner->tree.end()}).first);
        const std::string indentation = parent_indentation + indentation_unit(doc);
        if (is_blank(slice(current, open, close))) {
            // {} (or only whitespace between): {, the lines, the parent's indentation, }.
            const insert ins = insert_of(text, append(append({eol}, lines(indentation)), {eol, parent_indentation}));
            return created_statements(splice(doc, open, close, ins, given), block->owner);
        }
        // Only comments inside: the lines go before the } line.
        const std::int64_t line_start = last_index_of(current, '\n', close - 1) + 1;
        if (only_blanks(slice(current, line_start, close), false)) {
            at = line_start;
            pieces = append(lines(indentation), {eol});
        } else {
            at = close;
            pieces = append(append({eol}, lines(indentation)), {eol, parent_indentation});
        }
    }
    return created_statements(splice(doc, at, at, insert_of(text, pieces), given), block->owner);
}

/// rename of a directive: its name token. A bad name is a misuse error; the statement keeps its handle.
inline void rename_statement(statement_node* s, std::string_view name) {
    check_directive_name(name);
    const token_info& token = s->doc->parsed.at(s->tree.start());
    splice(s->doc, static_cast<std::int64_t>(token.start), static_cast<std::int64_t>(token.end), insert_of(name), {},
           s);
}

/// rename of a set variable or a parameter: its $name token only. A second set of the name in its block is E5002, by
/// the text-alone rules. The variable keeps its handle.
inline void rename_variable(document_node* doc, std::int64_t token, std::string_view name, handle_node* keep) {
    check_variable_name(name);
    const token_info& at = doc->parsed.at(token);
    splice(doc, static_cast<std::int64_t>(at.start), static_cast<std::int64_t>(at.end),
           insert_of(name, {std::string("$"),
                            std::pair<std::int64_t, std::int64_t>(0, static_cast<std::int64_t>(name.size()))}),
           {}, keep);
}

/// The offsets [start, end) of a value's tokens.
inline std::pair<std::int64_t, std::int64_t> value_offsets(const value_node* v) {
    return offsets_of(v->doc->parsed, {v->ref.start, v->ref.end});
}

/// set of a statement's values (spec 6.5): first value to last; with none, after token `after`. A text that holds no
/// value must be empty: set("") clears the values, set("# c\n") is E2001 at 0:0.
inline void replace_values(statement_node* s, std::int64_t after, std::string_view text) {
    document_node* doc = s->doc;
    const parsed_text syntax = parse_entry(text, entry_rule::values_text);
    const std::vector<::knobly::diagnostic> given = diagnostics_of(syntax);
    if (given.empty() && !text.empty() && values_of(syntax).empty()) {
        ::knobly::detail::raise(
            ::knobly::bad_text_error({diagnostic_at(text, 0, ::knobly::diagnostic_code::unexpected_token)}));
    }
    const parsed_text& p = doc->parsed;
    const std::vector<value_node*>& values = s->values;
    if (values.empty()) {
        if (text.empty()) {
            return;
        }
        const auto offset = static_cast<std::int64_t>(p.has(after) ? p.at(after).end : 0);
        splice(doc, offset, offset,
               insert_of(text, {std::string(" "),
                                std::pair<std::int64_t, std::int64_t>(0, static_cast<std::int64_t>(text.size()))}),
               given);
        return;
    }
    const std::int64_t start = value_offsets(values.front()).first;
    const std::int64_t end = value_offsets(values.back()).second;
    if (text.empty()) {
        std::int64_t from = values.front()->ref.start;
        while (p.is(from - 1, ::knobly::token_kind::SPACE)) {
            --from;
        }
        splice(doc, p.has(from) ? static_cast<std::int64_t>(p.at(from).start) : start, end, insert_of(""), given);
        return;
    }
    splice(doc, start, end, insert_of(text), given);
}

/// A value's set (spec 6.1, 6.6): exactly one value (valueText; a bound boundText, a slice's name sliceNameText), in
/// place of this one, keeping its handle, which takes the new value's kind.
inline void set_value(value_node* v, std::string_view text) {
    const entry_rule rule = v->role == value_role::bound  ? entry_rule::bound_text
                            : v->role == value_role::name ? entry_rule::slice_name_text
                                                          : entry_rule::value_text;
    const std::vector<::knobly::diagnostic> given = diagnostics_of(parse_entry(text, rule));
    const auto [start, end] = value_offsets(v);
    splice(v->doc, start, end, insert_of(text), given, v);
}

/// Whether a bound is its slice's or index's only one (b[1], x[0~]): removing it leaves no bound (spec 6.6).
inline bool is_only_bound(const value_node* bound) {
    const parsed_text& p = bound->doc->parsed;
    std::int64_t open = bound->ref.start;
    while (open > 0 && !p.is(open, ::knobly::token_kind::LBRACK)) {
        --open;
    }
    int bounds = 0;
    for (std::int64_t i = open + 1; i < p.size() && !p.is(i, ::knobly::token_kind::RBRACK); ++i) {
        if (p.is(i, ::knobly::token_kind::INTEGER) || p.is(i, ::knobly::token_kind::VARIABLE)) {
            ++bounds;
        }
    }
    return bounds <= 1;
}

/// remove() of a value (spec 6.6): with the space before it. In a list, the item and its comma only (the one after
/// it, else the one before it); comments and line breaks between them stay, and a line left empty goes.
inline void remove_value(value_node* v) {
    using ::knobly::token_kind;
    document_node* doc = v->doc;
    const parsed_text& p = doc->parsed;
    const std::string_view current = p.text;
    if (v->role == value_role::name || (v->role == value_role::bound && is_only_bound(v))) {
        ::knobly::detail::raise(::knobly::misuse_error(
            "remove(): a slice's or index's name, and its only bound, cannot be removed: set it, or remove the slice"));
    }
    const auto [start, end] = value_offsets(v);
    if (v->list != nullptr) {
        const auto skipped = [&](std::int64_t i) {
            return p.is(i, token_kind::SPACE) || p.is(i, token_kind::NEWLINE) || p.is(i, token_kind::COMMENT);
        };
        const std::int64_t first = v->ref.start;
        const std::int64_t last = v->ref.end - 1;
        std::int64_t after = last + 1;
        while (skipped(after)) {
            ++after;
        }
        if (p.is(after, token_kind::COMMA)) {
            const auto comma_end = static_cast<std::int64_t>(p.at(after).end);
            const std::string_view between = slice(current, end, static_cast<std::int64_t>(p.at(after).start));
            if (only_blanks(between, false)) {
                const auto [from, to] = removal_range(doc, start, comma_end);
                splice(doc, from, to, insert_of(""), {});
            } else {
                splice(doc, start, comma_end, insert_of(std::string(between.substr(leading_blanks(between).size()))),
                       {});
            }
            return;
        }
        std::int64_t before = first - 1;
        while (skipped(before)) {
            --before;
        }
        if (p.is(before, token_kind::COMMA)) {
            const auto comma_start = static_cast<std::int64_t>(p.at(before).start);
            std::string_view between = slice(current, static_cast<std::int64_t>(p.at(before).end), start);
            if (only_blanks(between, false)) {
                between = {};
            } else {
                while (!between.empty() && (between.back() == ' ' || between.back() == '\t')) {
                    between.remove_suffix(1);
                }
            }
            splice(doc, comma_start, end, insert_of(std::string(between)), {});
            return;
        }
        splice(doc, start, end, insert_of(""), {});
        return;
    }
    std::int64_t from = v->ref.start;
    while (p.is(from - 1, token_kind::SPACE)) {
        --from;
    }
    splice(doc, p.has(from) ? static_cast<std::int64_t>(p.at(from).start) : start, end, insert_of(""), {});
}

/// replace_with_text of a value, checked with the entry rule for where it stands (spec 2.8): boundText for a slice
/// bound, itemsText for a list item, else valuesText.
inline std::vector<value_node*> replace_value(value_node* v, std::string_view text) {
    const entry_rule rule = v->role == value_role::bound  ? entry_rule::bound_text
                            : v->role == value_role::name ? entry_rule::slice_name_text
                            : v->list != nullptr          ? entry_rule::items_text
                                                          : entry_rule::values_text;
    const std::vector<::knobly::diagnostic> given = diagnostics_of(parse_entry(text, rule));
    if (v->role != value_role::value && !given.empty()) {
        ::knobly::detail::raise(::knobly::bad_text_error(given));
    }
    if (is_blank(text)) {
        if (!given.empty()) {
            ::knobly::detail::raise(::knobly::bad_text_error(given));
        }
        remove_value(v);
        return {};
    }
    const auto [start, end] = value_offsets(v);
    value_node* const container = v->list;
    statement_node* const statement = v->statement;
    const value_role role = v->role;
    std::vector<value_node*> out;
    for (handle_node* h : splice(v->doc, start, end, insert_of(text), given)) {
        if (h->family != 'v') {
            continue;
        }
        auto* made = static_cast<value_node*>(h);
        if (made->list == container && made->statement == statement && made->role == role) {
            out.push_back(made);
        }
    }
    return out;
}

// ---- declarations by where written (spec 6.7)

/// The block holding a statement: its parent's, or its document's top level.
inline block_node* containing_block(const statement_node* s) {
    return s->parent != nullptr && s->parent->block != nullptr ? s->parent->block : s->doc->block;
}

inline std::int64_t position_of(const std::vector<statement_node*>& items, const statement_node* s) {
    const auto found = std::find(items.begin(), items.end(), s);
    return found == items.end() ? -1 : static_cast<std::int64_t>(found - items.begin());
}

/// The token index of a statement's first value-position token (a set's $name, a snippet's or use's name).
inline std::int64_t first_arg_token(const statement_node* s) {
    const anatomy a = anatomy_of(s->doc->parsed, s->tree);
    return a.values.empty() || !a.values.front().is_token() ? s->tree.start() : a.values.front().start;
}

/// The name a set line's $name gives (without $).
inline std::string set_variable_name(const statement_node* line) {
    return std::string(line->doc->parsed.text_at(first_arg_token(line)).substr(1));
}

/// A parameter's name (without $).
inline std::string parameter_name(const variable_node* parameter) {
    return std::string(parameter->line->doc->parsed.text_at(parameter->token).substr(1));
}

/// The variable a reference binds to by where it is written; null when free. Nearest first, as the binding picks:
/// block by block outward, the set lines above in that block, then the parameters of the snippet whose body it is.
inline variable_node* declaration_of(const value_node* reference) {
    const std::string name(reference->doc->parsed.text_of(reference->ref.start, reference->ref.end).substr(1));
    for (statement_node* s = reference->statement; s != nullptr; s = s->parent) {
        statement_node* const parent = s->parent;
        const std::vector<statement_node*>& items =
            (parent != nullptr && parent->block != nullptr ? parent->block : reference->doc->block)->handles;
        for (std::int64_t i = position_of(items, s) - 1; i >= 0; --i) {
            statement_node* const candidate = items[static_cast<std::size_t>(i)];
            if (candidate->kind == ::knobly::statement_kind::set && set_variable_name(candidate) == name) {
                return candidate->variable;
            }
        }
        if (parent != nullptr && parent->kind == ::knobly::statement_kind::snippet) {
            for (variable_node* parameter : parent->parameters) {
                if (parameter_name(parameter) == name) {
                    return parameter;
                }
            }
        }
    }
    return nullptr;
}

/// The nearest statement above `statement` in its block or an enclosing block that matches.
template <class Match>
statement_node* above(statement_node* statement, Match&& match) {
    for (statement_node* s = statement; s != nullptr; s = s->parent) {
        const std::vector<statement_node*>& items = containing_block(s)->handles;
        for (std::int64_t i = position_of(items, s) - 1; i >= 0; --i) {
            statement_node* const candidate = items[static_cast<std::size_t>(i)];
            if (match(candidate)) {
                return candidate;
            }
        }
    }
    return nullptr;
}

/// Every reference value of a document, in text order.
inline void references_of(const document_node* doc, std::vector<value_node*>& out) {
    std::function<void(value_node*)> value = [&](value_node* v) {
        if (v->kind == ::knobly::value_kind::reference) {
            out.push_back(v);
        }
        for (value_node* inner : inner_handles(v)) {
            value(inner);
        }
    };
    std::function<void(statement_node*)> statement = [&](statement_node* s) {
        for (value_node* v : s->values) {
            value(v);
        }
        if (s->block != nullptr) {
            for (statement_node* child : s->block->handles) {
                statement(child);
            }
        }
    };
    for (statement_node* s : doc->block->handles) {
        statement(s);
    }
}

/// Every set line's and snippet line's variables of a document, in text order.
inline void variables_of(const document_node* doc, std::vector<variable_node*>& out) {
    std::function<void(statement_node*)> statement = [&](statement_node* s) {
        if (s->kind == ::knobly::statement_kind::set) {
            out.push_back(s->variable);
        }
        if (s->kind == ::knobly::statement_kind::snippet) {
            out.insert(out.end(), s->parameters.begin(), s->parameters.end());
        }
        if (s->block != nullptr) {
            for (statement_node* child : s->block->handles) {
                statement(child);
            }
        }
    };
    for (statement_node* s : doc->block->handles) {
        statement(s);
    }
}

}  // namespace written::detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_EDITS_HPP
