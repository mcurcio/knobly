// The written layer's nodes (design.md 2.3; frozen-m2.md 3.1, 4): what each handle class's view points at. A graph's
// core is a counted node; its documents, statements, values and variables live in its arena and name it as their
// counted owner, so a view of any of them keeps the whole graph alive, and a detached node stays until the graph dies
// (design.md 2.3). A binding (one derivation of the graph, bind.hpp) is a counted node inside the graph: its copies,
// edges, resolutions, expanded values and expansion live in its arena, and a view of one keeps the binding and the
// graph alive. Package-internal: programs see the generated handle classes (written.hpp).
#ifndef VILLANELLE_DETAIL_WRITTEN_CORE_HPP
#define VILLANELLE_DETAIL_WRITTEN_CORE_HPP

#include <cstddef>
#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

#include <villanelle/detail/raise.hpp>
#include <villanelle/support/view.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace written::detail {

using ::villanelle::detail::node;

// ---- one text and its parse

/// One token of a parse: its kind, its byte range, its span.
struct token_info {
    ::villanelle::token_kind kind;
    std::size_t start;
    std::size_t end;
    ::villanelle::source_span span;
};

/// A text and its parse (a document's, an override's or an edit's), with the tokens read once.
struct parsed_text {
    std::string text;
    ::villanelle::syntax::syntax syntax;
    std::vector<token_info> tokens;

    parsed_text(std::string source, ::villanelle::syntax::syntax parsed)
        : text(std::move(source)), syntax(std::move(parsed)) {
        tokens.reserve(syntax.tokens().size());
        for (const ::villanelle::syntax::token& token : syntax.tokens()) {
            const ::villanelle::source_span span = token.span();
            tokens.push_back({token.kind(), static_cast<std::size_t>(span.start().offset()),
                              static_cast<std::size_t>(span.end().offset()), span});
        }
    }

    std::int64_t size() const noexcept { return static_cast<std::int64_t>(tokens.size()); }
    bool has(std::int64_t i) const noexcept { return i >= 0 && i < size(); }
    /// Whether token i exists and is of `kind` (TypeScript's tokens[i]?.kind === kind).
    bool is(std::int64_t i, ::villanelle::token_kind kind) const noexcept {
        return has(i) && tokens[static_cast<std::size_t>(i)].kind == kind;
    }
    const token_info& at(std::int64_t i) const { return tokens[static_cast<std::size_t>(i)]; }
    /// Token i's text; empty past the end.
    std::string_view text_at(std::int64_t i) const noexcept {
        if (!has(i)) {
            return {};
        }
        const token_info& token = at(i);
        return std::string_view(text).substr(token.start, token.end - token.start);
    }
    /// Token i's start offset; 0 past the end.
    std::size_t start_of(std::int64_t i) const noexcept { return has(i) ? at(i).start : 0; }
    /// The position just after the text.
    ::villanelle::source_position text_end() const noexcept {
        return tokens.empty() ? ::villanelle::source_position(0, 0, 0) : tokens.back().span.end();
    }
    /// The span of the token range [start, end) (syntax::span_of, without its range check).
    ::villanelle::source_span span_of(std::int64_t start, std::int64_t end) const noexcept {
        const ::villanelle::source_position first = has(start) ? at(start).span.start() : text_end();
        if (start >= end) {
            return {first, first};
        }
        return {first, at(end - 1).span.end()};
    }
    /// The byte offsets [start, end) of a token range.
    std::pair<std::size_t, std::size_t> offsets(std::int64_t start, std::int64_t end) const noexcept {
        const ::villanelle::source_span span = span_of(start, end);
        return {static_cast<std::size_t>(span.start().offset()), static_cast<std::size_t>(span.end().offset())};
    }
    /// The text of a token range.
    std::string text_of(std::int64_t start, std::int64_t end) const {
        const auto [from, to] = offsets(start, end);
        return text.substr(from, to - from);
    }
};

/// A written value's tokens: one token, or a list or slice node.
struct value_ref {
    std::int64_t start = 0;
    std::int64_t end = 0;
    std::optional<::villanelle::syntax::node> tree;  // the list or slice node; empty for one token

    static value_ref token(std::int64_t at) { return {at, at + 1, std::nullopt}; }
    static value_ref of(const ::villanelle::syntax::node& n) { return {n.start(), n.end(), n}; }
    bool is_token() const noexcept { return !tree.has_value(); }
};

/// Which parts of a directive node are its name, its values and its block (anatomy.ts).
struct anatomy {
    std::int64_t name = 0;
    std::vector<value_ref> values;
    std::optional<::villanelle::syntax::node> block;
};

// ---- arenas

/// The nodes a counted node owns: each names that node as its counted owner, and dies with it.
struct arena {
    explicit arena(node* owner) noexcept : owner_(owner) {}
    template <class T, class... Args>
    T* make(Args&&... args) {
        auto made = std::make_unique<T>(std::forward<Args>(args)...);
        made->counted = owner_;
        T* const raw = made.get();
        nodes_.push_back(std::move(made));
        return raw;
    }

private:
    node* owner_;
    std::vector<std::unique_ptr<node>> nodes_;
};

/// A generated handle class over a node.
template <class Handle>
Handle make_handle(node* n) {
    return ::villanelle::detail::access::make<Handle>(::villanelle::detail::view(n));
}

/// The node a handle shows.
template <class Node, class Handle>
Node* node_of(const Handle& handle) noexcept {
    return static_cast<Node*>(::villanelle::detail::access::view_of(handle).get());
}

// ---- the graph's nodes

struct graph_core;
struct document_node;
struct statement_node;
struct value_node;
struct variable_node;
struct binding_core;
struct copy_node;
struct resolution_node;
struct expanded_node;

/// What a reconcile keeps or detaches (a statement, a value, a parameter).
struct handle_node : node {
    explicit handle_node(char f) noexcept : family(f) {}
    char family;  // 's' a statement, 'v' a value, 'p' a variable (a parameter, in a reconcile)
    bool detached = false;
};

/// The statements of a document's top level or of a statement's block (spec 2.11): live, rebuilt by every parse.
struct block_node : node {
    document_node* doc = nullptr;
    statement_node* owner = nullptr;  // null: the document's top level
    std::vector<statement_node*> handles;
};

struct statement_node : handle_node {
    statement_node(::villanelle::statement_kind k, document_node* d)
        : handle_node('s'), kind(k), doc(d), tree(0, 0, ::villanelle::node_kind::error, {}) {}
    ::villanelle::statement_kind kind;
    document_node* doc;
    ::villanelle::syntax::node tree;  // its directive or error node in the current parse
    statement_node* parent = nullptr;
    std::vector<value_node*> values;  // none for a snippet or unreadable line
    block_node* block = nullptr;
    std::vector<variable_node*> parameters;  // a snippet line's
    variable_node* variable = nullptr;       // a set line's, made with it
};

/// Where a value stands, which decides the entry rule its edits take (spec 2.8).
enum class value_role : std::uint8_t { value, bound, name };

struct value_node : handle_node {
    value_node(::villanelle::value_kind k, document_node* d) : handle_node('v'), kind(k), doc(d) {}
    ::villanelle::value_kind kind;
    document_node* doc;
    value_ref ref;
    statement_node* statement = nullptr;
    value_node* list = nullptr;
    value_role role = value_role::value;
    // Every kind's inner handles, on the one node so a value can change kind (spec 6.1).
    std::vector<value_node*> items;
    value_node* name = nullptr;
    value_node* start = nullptr;
    value_node* end = nullptr;
    value_node* index = nullptr;
};

struct variable_node : handle_node {
    explicit variable_node(::villanelle::variable_kind k) : handle_node('p'), kind(k) {}
    ::villanelle::variable_kind kind;
    statement_node* line = nullptr;  // a set variable's set line, a parameter's snippet line
    std::int64_t token = 0;          // a parameter's VARIABLE token in the current parse
    std::string name;                // an override's name
    graph_core* graph = nullptr;     // an override's graph
};

struct document_node : node {
    document_node(graph_core* g, std::string resolved, parsed_text text)
        : graph(g), path(std::move(resolved)), parsed(std::move(text)), saved(parsed.text) {}
    graph_core* graph;
    std::string path;
    parsed_text parsed;
    std::string saved;
    block_node* block = nullptr;
    std::unordered_map<std::int64_t, statement_node*> statements_by_token;
    std::unordered_map<std::int64_t, value_node*> values_by_token;
};

// ---- a binding's nodes

/// One copy of a statement: the statement, and the steps that brought it there.
struct copy_node : node {
    copy_node(statement_node* s, ::villanelle::sequence<::villanelle::step> v) : statement(s), via(std::move(v)) {}
    statement_node* statement;
    ::villanelle::sequence<::villanelle::step> via;
};

struct edge_node : node {
    explicit edge_node(copy_node* c) : copy(c) {}
    copy_node* copy;
    std::vector<std::string> specs;
    std::vector<std::string> targets;
};

/// A resolution at one copy: a reference's (winner and shadowed are variables) or a use line's (snippet lines).
struct resolution_node : node {
    explicit resolution_node(copy_node* c) : copy(c) {}
    copy_node* copy;
    node* winner = nullptr;
    std::vector<node*> shadowed;
    value_node* reference = nullptr;  // a reference resolution's
    std::vector<value_node*> values;  // its winner's values as written
};

/// One value after expansion (value.ts ExpandedRecord): kind, canonical text, origin and links.
struct expanded_node : node {
    explicit expanded_node(::villanelle::origin o) : origin(std::move(o)) {}
    ::villanelle::value_kind kind = ::villanelle::value_kind::word;
    std::string text;   // canonical
    std::string value;  // a word's text, a string's decoded value
    std::vector<expanded_node*> items;
    std::string name;
    std::optional<std::int64_t> start;
    std::optional<std::int64_t> end;
    std::int64_t index = 0;
    ::villanelle::origin origin;
    value_node* definition = nullptr;     // the written value at the end of its chain; null for an override's
    std::vector<resolution_node*> chain;  // one per variable step, the statement's own $name first
};

struct directive_expansion_node;
struct unreadable_node;

/// An expansion block's items: a snapshot.
struct expansion_block_node : node {
    std::vector<directive_expansion_node*> items;
};

struct directive_expansion_node : node {
    directive_expansion_node(statement_node* w, ::villanelle::directive_origin o) : written(w), origin(std::move(o)) {}
    statement_node* written;
    ::villanelle::directive_origin origin;
    std::vector<expanded_node*> values;
    expansion_block_node* block = nullptr;
    std::vector<unreadable_node*> unreadable;
};

struct unreadable_node : node {
    unreadable_node(statement_node* w, ::villanelle::unreadable_reason r, ::villanelle::directive_origin o)
        : written(w), reason(r), origin(std::move(o)) {}
    statement_node* written;
    ::villanelle::unreadable_reason reason;
    ::villanelle::directive_origin origin;
};

struct expansion_node : node {
    expansion_block_node* block = nullptr;
    std::vector<unreadable_node*> unreadable;
    std::vector<::villanelle::located_diagnostic> diagnostics;
};

/// What one container (the root's top level, or a directive's block) holds at one copy, in walk order.
struct bound_item {
    bool directive = false;
    copy_node* copy = nullptr;
    bool has_children = false;  // a directive written with a block
    std::vector<bound_item> children;
    ::villanelle::unreadable_reason reason = ::villanelle::unreadable_reason::syntax;
};

/// What an unread edge still needs from the source: specs to resolve, or paths to read.
struct read_need {
    bool resolve = true;
    std::string parent_path;
    std::vector<std::string> specs;
    std::vector<std::string> paths;
};

/// One derivation of the graph's texts, overrides and read ledger (bind.ts Binding). Immutable once made; the graph
/// makes a new one after any edit, set_override or read.
struct binding_core : node {
    explicit binding_core(graph_core* g);
    arena nodes{this};
    graph_core* graph;
    std::vector<bound_item> items;
    std::vector<edge_node*> edges;
    std::vector<edge_node*> unread;
    std::vector<::villanelle::located_diagnostic> diagnostics;
    std::map<edge_node*, read_need> needs;
    std::unordered_map<statement_node*, std::vector<copy_node*>> copies;
    std::unordered_map<value_node*, std::vector<resolution_node*>> by_reference;
    std::vector<resolution_node*> resolutions;
    std::unordered_map<statement_node*, std::vector<resolution_node*>> by_use;
    /// Per directive copy, each written value's expanded values; absent for a copy whose values did not expand.
    std::unordered_map<copy_node*, std::unordered_map<value_node*, std::vector<expanded_node*>>> expanded;
    // The graph-level caches of this version.
    std::optional<std::vector<::villanelle::located_diagnostic>> all_diagnostics;
    expansion_node* expansion = nullptr;
};

/// An override's values, read from its checked text; `problem` is the E4001 detail of a literal bound beyond the
/// integer range, which makes every $name it reaches unreadable.
struct override_values {
    std::vector<expanded_node*> values;
    std::optional<std::string> problem;
};

/// What the source said about one spec, or one read: the paths or text, or its failure's message.
struct ledger_entry {
    std::vector<std::string> paths;
    std::optional<std::string> failure;
};

struct graph_core : node {
    arena nodes{this};
    std::shared_ptr<::villanelle::document_source> source;
    std::vector<std::pair<std::string, std::shared_ptr<::villanelle::written::extension>>> extensions;
    std::set<std::string> extension_names;
    std::vector<document_node*> documents;  // in read order, the root first
    ::villanelle::ordered_map<std::string, ::villanelle::config_text> override_texts;
    std::map<std::string, override_values> overrides;
    std::map<std::string, variable_node*> override_variables;  // kept for the graph's life
    std::map<std::pair<std::string, std::string>, ledger_entry> resolved;
    std::map<std::string, std::string> failed_reads;
    std::uint64_t version = 0;
    binding_core* binding = nullptr;  // the cache, held (one count); its version below
    std::uint64_t binding_version = 0;

    graph_core() = default;
    graph_core(const graph_core&) = delete;
    graph_core& operator=(const graph_core&) = delete;
    ~graph_core() override { drop_binding(); }

    void drop_binding() noexcept {
        if (binding != nullptr && binding->count.fetch_sub(1, std::memory_order_acq_rel) == 1) {
            delete binding;
        }
        binding = nullptr;
    }
    document_node* document(std::string_view path) const {
        for (document_node* doc : documents) {
            if (doc->path == path) {
                return doc;
            }
        }
        return nullptr;
    }
};

inline binding_core::binding_core(graph_core* g) : graph(g) { outer = g; }

/// The processor's state (spec 6.2): its source and extensions, by name.
struct processor_node : node {
    std::shared_ptr<::villanelle::document_source> source;
    std::vector<std::pair<std::string, std::shared_ptr<::villanelle::written::extension>>> extensions;
};

// ---- liveness (contract 4.3: every member but kind() of a detached handle raises detached_error first)

[[noreturn]] inline void raise_detached(std::string_view what) {
    ::villanelle::detail::raise(::villanelle::detached_error(
        "this " + std::string(what) + " was removed by an edit or its document's text was replaced"));
}

inline statement_node* live(statement_node* s) {
    if (s->detached) {
        raise_detached("statement");
    }
    return s;
}

inline value_node* live(value_node* v) {
    if (v->detached) {
        raise_detached("value");
    }
    return v;
}

/// A set variable lives while its set line does; a parameter is detached itself, or with its snippet line.
inline variable_node* live(variable_node* v) {
    if (v->kind == ::villanelle::variable_kind::parameter && v->detached) {
        raise_detached("parameter");
    }
    if (v->line != nullptr) {
        live(v->line);
    }
    return v;
}

/// A stale variant view's own member (finding F4): the node changed kind under set.
inline void require_kind(const value_node* v, ::villanelle::value_kind kind, std::string_view member) {
    if (v->kind != kind) {
        ::villanelle::detail::raise(::villanelle::misuse_error(
            std::string(member) + "(): this value is now a " + std::string(to_string(v->kind)) + ", not a " +
            std::string(to_string(kind)) + " (set changed its kind)"));
    }
}

}  // namespace written::detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_CORE_HPP
