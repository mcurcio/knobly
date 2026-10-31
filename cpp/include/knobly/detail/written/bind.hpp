// The binding (ts/src/written/bind.ts): one derivation of the graph's current texts, overrides and read ledger. It
// walks the copies (the root, then each include and use spliced in place), decides per copy what each $name and use
// reads, and expands written values for the extension lines and for the expansion: the one home of the name-lookup
// rule (spec/expansion.md). Pure: no input or output (the read ledger stands in for the files). A statement that
// cannot be read is a `problem` returned up the walk (no exceptions: frozen-m2.md 3.3 rule 7), kept unreadable where
// the statement is. Package-internal.
#ifndef KNOBLY_DETAIL_WRITTEN_BIND_HPP
#define KNOBLY_DETAIL_WRITTEN_BIND_HPP

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <exception>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

#include <knobly/detail/raise.hpp>
#include <knobly/detail/shared/rules.hpp>
#include <knobly/detail/written/core.hpp>
#include <knobly/detail/written/edits.hpp>
#include <knobly/detail/written/entry.hpp>
#include <knobly/detail/written/shape.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace written::detail {

// ---- expanded values (value.ts ExpandedRecord)

/// What an expanded value holds, by kind.
struct expanded_data {
    ::knobly::value_kind kind = ::knobly::value_kind::word;
    std::string value;  // a word's text, a string's decoded value
    std::vector<expanded_node*> items;
    std::string name;
    std::optional<std::int64_t> start;
    std::optional<std::int64_t> end;
    std::int64_t index = 0;
};

/// The canonical text of a value (spec 2.9).
inline std::string canonical_text_of(const expanded_data& data) {
    switch (data.kind) {
        case ::knobly::value_kind::string:
            return ::knobly::detail::rules::canonical_string(data.value);
        case ::knobly::value_kind::list: {
            std::string out = "[";
            for (std::size_t i = 0; i < data.items.size(); ++i) {
                if (i > 0) {
                    out += ", ";
                }
                out += data.items[i]->text;
            }
            return out + "]";
        }
        case ::knobly::value_kind::slice:
            return ::knobly::detail::rules::canonical_slice(data.name, data.start, data.end);
        case ::knobly::value_kind::index:
            return ::knobly::detail::rules::canonical_index(data.name, data.index);
        default:
            return data.value;
    }
}

inline expanded_node* make_expanded(arena& a, expanded_data data, ::knobly::origin origin,
                                    value_node* definition = nullptr, std::vector<resolution_node*> chain = {}) {
    expanded_node* made = a.make<expanded_node>(std::move(origin));
    made->text = canonical_text_of(data);
    made->kind = data.kind;
    made->value = std::move(data.value);
    made->items = std::move(data.items);
    made->name = std::move(data.name);
    made->start = data.start;
    made->end = data.end;
    made->index = data.index;
    made->definition = definition;
    made->chain = std::move(chain);
    return made;
}

/// The same value having travelled further: the last `drop` steps of its origin (and of each list item's) are replaced
/// by `append`, and `resolution` (when given) leads its chain. A variable's value is stored with drop = the set line's
/// own steps, and read with append = the variable step and the reading place's steps. A loop, not a recursion: a list
/// may be max_expanded_nesting deep (spec 2.5). Each list is made after its items, which wait on `made` in order.
inline expanded_node* rebase(arena& a, const expanded_node* value, std::size_t drop,
                             const std::vector<::knobly::step>& append, resolution_node* resolution) {
    std::vector<expanded_node*> made;
    std::vector<std::pair<const expanded_node*, bool>> stack{
        {value, false}};  // a value, and whether its items are made
    while (!stack.empty()) {
        const auto [at, items_made] = stack.back();
        stack.pop_back();
        if (!at->items.empty() && !items_made) {
            stack.emplace_back(at, true);
            for (auto item = at->items.rbegin(); item != at->items.rend(); ++item) {
                stack.emplace_back(*item, false);
            }
            continue;
        }
        const ::knobly::sequence<::knobly::step> old = at->origin.via();
        std::vector<::knobly::step> via(old.begin(), old.begin() + static_cast<std::ptrdiff_t>(old.size() - drop));
        via.insert(via.end(), append.begin(), append.end());
        expanded_data data{at->kind, at->value, {}, at->name, at->start, at->end, at->index};
        const auto first = made.end() - static_cast<std::ptrdiff_t>(at->items.size());
        data.items.assign(first, made.end());
        made.erase(first, made.end());
        std::vector<resolution_node*> chain;
        if (resolution != nullptr) {
            chain.push_back(resolution);
        }
        chain.insert(chain.end(), at->chain.begin(), at->chain.end());
        made.push_back(make_expanded(a, std::move(data), ::knobly::origin(at->origin.place(), std::move(via)),
                                     at->definition, std::move(chain)));
    }
    return made.front();
}

// ---- problems

/// Why a statement cannot be read at a copy; `diagnostic` is absent when the problem is already one of a document's
/// syntax diagnostics. `value`: a problem with one of a directive's values (bind.ts ValueProblem).
struct problem {
    ::knobly::unreadable_reason reason;
    std::optional<::knobly::located_diagnostic> diagnostic;
    bool value = false;
};
using failure = std::optional<problem>;

/// A statement's problem with knobly's code: its message and its unreadable reason, from the code.
inline problem located(::knobly::diagnostic_code code, const ::knobly::place& place,
                       const std::vector<::knobly::step>& via, const std::optional<std::string>& detail) {
    const ::knobly::described d = detail ? ::knobly::describe(code, *detail) : ::knobly::describe(code);
    return {d.reason.value_or(::knobly::unreadable_reason::expansion),
            ::knobly::located_diagnostic(code, d.message, place, via)};
}

// ---- scopes (spec/expansion.md)

/// One text being walked: a document, or an override's text.
struct text_ref {
    document_node* doc = nullptr;  // null for an override's text
    const parsed_text* parsed = nullptr;
    std::string resolved_path;
    std::string override_name;

    std::variant<::knobly::place, ::knobly::override> written(const ::knobly::source_span& span) const {
        if (doc == nullptr) {
            return ::knobly::override(override_name);
        }
        return place(span);
    }
    ::knobly::place place(const ::knobly::source_span& span) const { return {resolved_path, span}; }
};

inline text_ref document_text(document_node* doc) { return {doc, &doc->parsed, doc->path, {}}; }

/// One definition of a name: its variable, the values a reader gets (stored without the definer's steps), as written;
/// `problem` for an override whose values cannot be read.
struct definition {
    variable_node* variable = nullptr;
    std::vector<expanded_node*> values;
    std::vector<value_node*> written;
    std::optional<std::string> problem;
};

/// A definition visible at a place, by how the lookup treats it: a snippet parameter, a set, or an include block's set
/// (which wins over every set of the spliced files).
enum class entry_tag : std::uint8_t { parameter, set, forced };
struct entry {
    entry_tag tag;
    const definition* def;
};

struct scope_view;

/// A snippet definition: its parameters, its body, and the scope of the block it was written in (lexical).
struct snippet_def {
    std::string name;
    std::vector<std::string> params;
    ::knobly::syntax::node block;
    text_ref text;
    const scope_view* scope;
    statement_node* line;
};

/// What a place can see: variables and snippets, innermost first.
struct scope_view {
    scope_view() = default;
    scope_view(const scope_view&) = delete;
    scope_view& operator=(const scope_view&) = delete;
    virtual ~scope_view() = default;
    virtual void entries(const std::string& name, std::vector<entry>& out) const = 0;
    virtual void snippets(const std::string& name, std::vector<const snippet_def*>& out) const = 0;
};

/// A block's scope: it claims names for the one-per-block checks and binds them.
struct block_scope : scope_view {
    virtual bool claim(const std::string& name) = 0;
    virtual void bind(const std::string& name, const definition* def) = 0;
    virtual bool define(const snippet_def* snippet) = 0;
};

/// The variables and snippets of one block: its own lines so far, then the enclosing view's.
struct scope final : block_scope {
    explicit scope(const scope_view* outer) : outer_(outer) {}

    void entries(const std::string& name, std::vector<entry>& out) const override {
        if (const auto found = params_.find(name); found != params_.end()) {
            out.push_back({entry_tag::parameter, found->second});
        }
        if (const auto found = vars_.find(name); found != vars_.end()) {
            out.push_back({entry_tag::set, found->second});
        }
        if (outer_ != nullptr) {
            outer_->entries(name, out);
        }
    }
    void snippets(const std::string& name, std::vector<const snippet_def*>& out) const override {
        if (const auto found = defined_.find(name); found != defined_.end()) {
            out.push_back(found->second);
        }
        if (outer_ != nullptr) {
            outer_->snippets(name, out);
        }
    }
    bool claim(const std::string& name) override { return claimed_.insert(name).second; }
    void bind(const std::string& name, const definition* def) override { vars_[name] = def; }
    /// A snippet parameter: the body block's own binding of that name.
    void param(const std::string& name, const definition* def) {
        claimed_.insert(name);
        params_[name] = def;
    }
    bool define(const snippet_def* snippet) override { return defined_.emplace(snippet->name, snippet).second; }
    /// The variables this block bound itself (an extension block's set lines).
    const std::map<std::string, const definition*>& own() const noexcept { return vars_; }

private:
    const scope_view* outer_;
    std::map<std::string, const definition*> vars_;
    std::map<std::string, const definition*> params_;
    std::set<std::string> claimed_;
    std::map<std::string, const snippet_def*> defined_;
};

/// The including block's scope as a spliced file sees it: the file's top-level set and snippet lines claim, bind and
/// define in the including block, and the extension block's set lines win over every set of the spliced files, at any
/// depth, but not over a parameter.
struct splice_scope final : block_scope {
    splice_scope(block_scope* target, std::map<std::string, const definition*> forced)
        : target_(target), forced_(std::move(forced)) {}

    void entries(const std::string& name, std::vector<entry>& out) const override {
        if (const auto found = forced_.find(name); found != forced_.end()) {
            out.push_back({entry_tag::forced, found->second});
        }
        target_->entries(name, out);
    }
    void snippets(const std::string& name, std::vector<const snippet_def*>& out) const override {
        target_->snippets(name, out);
    }
    bool claim(const std::string& name) override { return target_->claim(name); }
    void bind(const std::string& name, const definition* def) override { target_->bind(name, def); }
    bool define(const snippet_def* snippet) override { return target_->define(snippet); }

private:
    block_scope* target_;
    std::map<std::string, const definition*> forced_;
};

/// The winner among `entries` (innermost first) and an override: the precedence table of spec/expansion.md, the one
/// home of the rule.
inline const definition* pick(const std::vector<entry>& entries, const definition* given) {
    const entry* found = nullptr;
    for (const entry& e : entries) {
        if (e.tag == entry_tag::parameter && found == nullptr) {
            return e.def;
        }
        if (e.tag == entry_tag::set && found == nullptr) {
            found = &e;
        }
        if (e.tag == entry_tag::forced) {
            found = &e;
            break;
        }
    }
    if (given != nullptr) {
        return given;
    }
    return found == nullptr ? nullptr : found->def;
}

/// Every visible definition in the order the rule picks them, each as if those before it were removed.
inline std::vector<const definition*> ordered(std::vector<entry> left, const definition* given) {
    std::vector<const definition*> out;
    for (;;) {
        const definition* next = pick(left, given);
        if (next == nullptr) {
            return out;
        }
        out.push_back(next);
        if (next == given) {
            given = nullptr;
        } else {
            left.erase(std::remove_if(left.begin(), left.end(), [&](const entry& e) { return e.def == next; }),
                       left.end());
        }
    }
}

/// A snippet or a file being walked around a place (the root file first).
using open_item = std::variant<const snippet_def*, std::string>;

/// One place statements are walked into.
struct place_context {
    text_ref text;
    block_scope* scope;
    std::vector<::knobly::step> via;  // innermost first
    std::vector<open_item> open;
    std::vector<bound_item>* into;
    /// The expanded blocks around this place (spec 2.5): a directive's block is one more; a snippet's body and a
    /// spliced file's top level stand where their line does.
    std::int64_t nesting = 0;
};

/// A block or a document's top level to walk, into a place.
struct opened {
    ::knobly::syntax::node block;
    place_context context;
};

/// How many lists deep the deepest of `values` goes (spec 2.5: a list is one level, a word none). A loop, not a
/// recursion: a value may hold lists up to max_expanded_nesting deep.
inline std::int64_t nesting_of(const std::vector<const expanded_node*>& values) {
    std::int64_t deepest = 0;
    std::vector<std::pair<const expanded_node*, std::int64_t>> stack;
    for (const expanded_node* v : values) {
        stack.emplace_back(v, 1);
    }
    while (!stack.empty()) {
        const auto [value, level] = stack.back();
        stack.pop_back();
        if (value->kind != ::knobly::value_kind::list) {
            continue;
        }
        deepest = std::max(deepest, level);
        for (const expanded_node* item : value->items) {
            stack.emplace_back(item, level + 1);
        }
    }
    return deepest;
}

inline std::vector<::knobly::step> with_step(::knobly::step first, const std::vector<::knobly::step>& via) {
    std::vector<::knobly::step> out{std::move(first)};
    out.insert(out.end(), via.begin(), via.end());
    return out;
}

// ---- the walk (bind.ts Walk)

class walk {
public:
    /// A walk filling `binding` (null for an override's values, whose records go to `records`).
    walk(binding_core* binding, arena& records, graph_core* graph) : binding_(binding), arena_(records), graph_(graph) {
        if (graph_ == nullptr || binding_ == nullptr) {
            return;
        }
        for (const auto& [name, values] : graph_->overrides) {
            const auto variable = graph_->override_variables.find(name);
            if (variable == graph_->override_variables.end()) {
                continue;
            }
            definition* def = keep(definition{variable->second, values.values, {}, values.problem});
            overrides_.emplace(name, def);
        }
    }

    /// The root document's top level at the root copy, includes and uses spliced in place.
    void run(document_node* root) {
        scope* top = make_scope(nullptr);
        walk_from(
            {root->parsed.syntax.root(), {document_text(root), top, {}, {open_item(root->path)}, &binding_->items, 0}});
    }

    /// One written value, expanded: a $name becomes all its values; a list's items expand the same way.
    failure value(const text_ref& text, const value_ref& ref, const scope_view& sc,
                  const std::vector<::knobly::step>& via, copy_node* copy, std::vector<expanded_node*>& out) {
        const parsed_text& p = *text.parsed;
        const ::knobly::origin origin(text.written(p.span_of(ref.start, ref.end)), via);
        value_node* const written = value_of(text, ref.start);
        if (!ref.is_token()) {
            if (ref.tree->kind() == ::knobly::node_kind::list) {
                std::vector<expanded_node*> items;
                for (const value_ref& item : items_of(p, *ref.tree)) {
                    if (failure f = value(text, item, sc, via, copy, items)) {
                        return f;
                    }
                }
                expanded_data data;
                data.kind = ::knobly::value_kind::list;
                data.items = std::move(items);
                out.push_back(make_expanded(arena_, std::move(data), origin, written));
                return std::nullopt;
            }
            return slice(text, *ref.tree, sc, via, copy, written, out);
        }
        const token_info& token = p.at(ref.start);
        if (is_word_kind(token.kind)) {
            expanded_data data;
            data.value = std::string(p.text_at(ref.start));
            out.push_back(make_expanded(arena_, std::move(data), origin, written));
            return std::nullopt;
        }
        if (token.kind == ::knobly::token_kind::STRING) {
            expanded_data data;
            data.kind = ::knobly::value_kind::string;
            data.value = ::knobly::detail::rules::decode_string(p.text_at(ref.start));
            out.push_back(make_expanded(arena_, std::move(data), origin, written));
            return std::nullopt;
        }
        return variable(text, ref.start, sc, via, copy,
                        written != nullptr && written->kind == ::knobly::value_kind::reference ? written : nullptr,
                        out);
    }

private:
    // ---- storage the walk keeps alive while it runs (scopes and snippets outlive the block that made them)

    scope* make_scope(const scope_view* outer) {
        scopes_.push_back(std::make_unique<scope>(outer));
        return static_cast<scope*>(scopes_.back().get());
    }
    definition* keep(definition def) {
        definitions_.push_back(std::move(def));
        return &definitions_.back();
    }

    value_node* value_of(const text_ref& text, std::int64_t token) const {
        if (text.doc == nullptr) {
            return nullptr;
        }
        const auto found = text.doc->values_by_token.find(token);
        return found == text.doc->values_by_token.end() ? nullptr : found->second;
    }

    copy_node* copy_of(statement_node* statement, const std::vector<::knobly::step>& via) {
        copy_node* copy = binding_->nodes.make<copy_node>(statement, ::knobly::sequence<::knobly::step>(via));
        binding_->copies[statement].push_back(copy);
        return copy;
    }

    problem at(::knobly::diagnostic_code code, const text_ref& text, const ::knobly::source_span& span,
               const std::vector<::knobly::step>& via, std::optional<std::string> detail = std::nullopt) const {
        return located(code, text.place(span), via, detail);
    }

    /// Walk statements depth first in written order (spec/expansion.md 2). A loop over a stack of open blocks, not a
    /// recursion: expansion nests blocks deeper than any one text (up to max_expanded_nesting, E5013), and a
    /// statement's own work is done before the blocks it opens are walked, so the stack keeps the order.
    void walk_from(opened start) {
        using children = ::knobly::sequence<::knobly::syntax::node>;
        struct open_block {
            children::iterator next;  // shares its list, as `end` does
            children::iterator end;
            place_context context;
        };
        const auto open = [](const ::knobly::syntax::node& block, place_context context) {
            const children items = block.children();
            return open_block{items.begin(), items.end(), std::move(context)};
        };
        std::vector<open_block> stack;
        stack.push_back(open(start.block, std::move(start.context)));
        std::vector<opened> blocks;
        while (!stack.empty() && !stopped_) {
            open_block& top = stack.back();
            if (top.next == top.end) {
                stack.pop_back();
                continue;
            }
            const ::knobly::syntax::node n = *top.next++;
            blocks.clear();
            item(n, top.context, blocks);  // `top` is not used after: pushing below may move it
            for (auto it = blocks.rbegin(); it != blocks.rend(); ++it) {
                stack.push_back(open(it->block, std::move(it->context)));
            }
        }
    }

    /// One statement of a walked block, kept readable or unreadable; the blocks it opens go to `blocks`, in walk order.
    void item(const ::knobly::syntax::node& n, place_context& context, std::vector<opened>& blocks) {
        document_node* const doc = context.text.doc;
        if (n.kind() != ::knobly::node_kind::directive && n.kind() != ::knobly::node_kind::error) {
            return;
        }
        copy_node* const copy = copy_of(doc->statements_by_token.at(n.start()), context.via);
        if (n.kind() == ::knobly::node_kind::error) {
            context.into->push_back(unreadable(copy, ::knobly::unreadable_reason::syntax));
            return;
        }
        if (failure f = statement(n, copy, context, blocks)) {
            blocks.clear();
            if (f->diagnostic) {
                binding_->diagnostics.push_back(*f->diagnostic);
            }
            if (f->value) {
                binding_->expanded.erase(copy);
            }
            context.into->push_back(unreadable(copy, f->reason));
        }
    }

    static bound_item unreadable(copy_node* copy, ::knobly::unreadable_reason reason) {
        bound_item item;
        item.copy = copy;
        item.reason = reason;
        return item;
    }

    /// One directive node. Its head's token kind decides (spec 2.5): an @ statement does its work; a WORD head is a
    /// directive, and its block is walked. The blocks it opens go to `blocks`.
    failure statement(const ::knobly::syntax::node& n, copy_node* copy, place_context& context,
                      std::vector<opened>& blocks) {
        const parsed_text& p = *context.text.parsed;
        const anatomy a = anatomy_of(p, n);
        const token_info& name = p.at(a.name);
        if (name.kind == ::knobly::token_kind::AT_WORD) {
            const std::string keyword(p.text_at(a.name).substr(1));
            const std::optional<::knobly::statement_kind> language = statement_of_keyword(keyword);
            if (language == ::knobly::statement_kind::set) {
                return set(a, copy, context.text, *context.scope, context.via, context.nesting);
            }
            if (language == ::knobly::statement_kind::snippet) {
                return snippet(a, copy, context);
            }
            if (language == ::knobly::statement_kind::use) {
                return use(a, name, copy, context, blocks);
            }
            for (const auto& [directive, extension] : graph_->extensions) {
                if (directive == keyword) {
                    return this->extension(directive, *extension, a, name, copy, context, blocks);
                }
            }
            return at(::knobly::diagnostic_code::unknown_extension, context.text, name.span, context.via,
                      std::string(p.text_at(a.name)));
        }
        statement_node* const statement = copy->statement;
        std::unordered_map<value_node*, std::vector<expanded_node*>> values;
        std::vector<const expanded_node*> all;
        for (value_node* v : statement->values) {
            std::vector<expanded_node*> out;
            if (failure f = value(context.text, v->ref, *context.scope, context.via, copy, out)) {
                f->value = true;
                return f;
            }
            all.insert(all.end(), out.begin(), out.end());
            values.emplace(v, std::move(out));
        }
        if (failure f = check_nesting(context.nesting, a.block.has_value(), all, context.text, name, context.via)) {
            return f;
        }
        binding_->expanded[copy] = std::move(values);
        if (++count_ > static_cast<std::size_t>(::knobly::written::max_directives)) {
            stopped_ = true;
            return at(::knobly::diagnostic_code::too_many_directives, context.text, name.span, context.via,
                      "more than " + std::to_string(::knobly::written::max_directives));
        }
        bound_item item;
        item.directive = true;
        item.copy = copy;
        item.has_children = a.block.has_value();
        context.into->push_back(std::move(item));
        if (a.block) {
            std::vector<bound_item>* children = &context.into->back().children;
            blocks.push_back(
                {*a.block,
                 {context.text, make_scope(context.scope), context.via, context.open, children, context.nesting + 1}});
        }
        return std::nullopt;
    }

    /// A set, snippet or use line's text-alone shape (shape.hpp, the one home of those rules), or its problem.
    failure well_formed(const anatomy& a, const text_ref& text, const std::vector<::knobly::step>& via) const {
        static const std::set<std::string> none;
        const shape s = shape_of_anatomy(*text.parsed, a, none);
        if (s.fault) {
            return at(s.fault->code, text, s.fault->span, via);
        }
        return std::nullopt;
    }

    /// @set $name value...; binds from this line to the end of the enclosing block. `nesting`: the expanded blocks
    /// around the line, for E5013.
    failure set(const anatomy& a, copy_node* copy, const text_ref& text, block_scope& sc,
                const std::vector<::knobly::step>& via, std::int64_t nesting) {
        if (failure f = well_formed(a, text, via)) {
            return f;
        }
        const parsed_text& p = *text.parsed;
        const std::int64_t variable = a.values.front().start;
        const std::string name(p.text_at(variable).substr(1));
        if (!sc.claim(name)) {
            return at(::knobly::diagnostic_code::variable_set_twice, text, p.at(variable).span, via,
                      std::string(p.text_at(variable)));
        }
        statement_node* const line = copy->statement;
        std::vector<expanded_node*> bound;
        for (std::size_t i = 1; i < a.values.size(); ++i) {
            if (failure f = value(text, a.values[i], sc, via, copy, bound)) {
                return f;
            }
        }
        if (failure f = check_nesting(nesting, false, {bound.begin(), bound.end()}, text, p.at(a.name), via)) {
            return f;
        }
        definition def{line->variable, {}, line->values, std::nullopt};
        for (const expanded_node* v : bound) {
            def.values.push_back(rebase(arena_, v, via.size(), {}, nullptr));
        }
        sc.bind(name, keep(std::move(def)));
        return std::nullopt;
    }

    /// @snippet name $param... { body }: visible from this line to the end of its block.
    failure snippet(const anatomy& a, copy_node* copy, place_context& context) {
        if (failure f = well_formed(a, context.text, context.via)) {
            return f;
        }
        const parsed_text& p = *context.text.parsed;
        const std::int64_t name = a.values.front().start;
        std::vector<std::string> params;
        for (std::size_t i = 1; i < a.values.size(); ++i) {
            params.emplace_back(p.text_at(a.values[i].start).substr(1));
        }
        statement_node* const line = copy->statement;
        bool defined = false;
        if (line->kind == ::knobly::statement_kind::snippet) {
            snippets_.push_back(snippet_def{std::string(p.text_at(name)), std::move(params), *a.block, context.text,
                                            context.scope, line});
            defined = context.scope->define(&snippets_.back());
        }
        if (!defined) {
            return at(::knobly::diagnostic_code::snippet_defined_twice, context.text, p.at(name).span, context.via,
                      std::string(p.text_at(name)));
        }
        return std::nullopt;
    }

    /// E5013 at the statement's name (spec 2.5): the line stands inside `nesting` expanded blocks, and its block (when
    /// `block`) or a list among its values would sit deeper than max_expanded_nesting. Checked before the values are
    /// kept or the block walked, so no walk over the expanded tree goes deeper.
    failure check_nesting(std::int64_t nesting, bool block, const std::vector<const expanded_node*>& values,
                          const text_ref& text, const token_info& name, const std::vector<::knobly::step>& via) const {
        if (std::max(nesting + (block ? 1 : 0), nesting + nesting_of(values)) >
            ::knobly::written::max_expanded_nesting) {
            return at(::knobly::diagnostic_code::expanded_nesting_too_deep, text, name.span, via);
        }
        return std::nullopt;
    }

    failure check_depth(const std::vector<open_item>& open, const text_ref& text, const token_info& name,
                        const std::vector<::knobly::step>& via) const {
        // `open` holds the root file and every expansion around this place: its length is this expansion's depth.
        if (static_cast<std::int64_t>(open.size()) > ::knobly::written::max_depth) {
            return at(::knobly::diagnostic_code::expansion_too_deep, text, name.span, via,
                      "more than " + std::to_string(::knobly::written::max_depth));
        }
        return std::nullopt;
    }

    /// @use name value...; the snippet's body, spliced in place with its parameters bound.
    failure use(const anatomy& a, const token_info& keyword, copy_node* copy, place_context& context,
                std::vector<opened>& blocks) {
        const text_ref& text = context.text;
        if (failure f = well_formed(a, text, context.via)) {
            return f;
        }
        const parsed_text& p = *text.parsed;
        const std::int64_t name_token = a.values.front().start;
        const std::string name(p.text_at(name_token));
        std::vector<const snippet_def*> visible;
        context.scope->snippets(name, visible);
        resolution_node* resolution = binding_->nodes.make<resolution_node>(copy);
        if (!visible.empty()) {
            resolution->winner = visible.front()->line;
            for (std::size_t i = 1; i < visible.size(); ++i) {
                resolution->shadowed.push_back(visible[i]->line);
            }
        }
        binding_->by_use[copy->statement].push_back(resolution);
        if (visible.empty()) {
            return at(::knobly::diagnostic_code::unknown_snippet, text, p.at(name_token).span, context.via, name);
        }
        const snippet_def* const snippet = visible.front();
        std::vector<value_node*> written;
        std::vector<expanded_node*> values;
        for (std::size_t i = 1; i < a.values.size(); ++i) {
            const std::size_t before = values.size();
            if (failure f = value(text, a.values[i], *context.scope, context.via, copy, values)) {
                return f;
            }
            value_node* const handle = value_of(text, a.values[i].start);
            written.insert(written.end(), values.size() - before, handle);
        }
        if (failure f =
                check_nesting(context.nesting, false, {values.begin(), values.end()}, text, keyword, context.via)) {
            return f;
        }
        if (values.size() != snippet->params.size()) {
            return at(
                ::knobly::diagnostic_code::snippet_arity, text, keyword.span, context.via,
                name + " takes " + std::to_string(snippet->params.size()) + ", given " + std::to_string(values.size()));
        }
        for (const open_item& item : context.open) {
            if (const auto* open = std::get_if<const snippet_def*>(&item); open != nullptr && *open == snippet) {
                return at(::knobly::diagnostic_code::expansion_cycle, text, keyword.span, context.via, name);
            }
        }
        if (failure f = check_depth(context.open, text, keyword, context.via)) {
            return f;
        }
        // Parameters are the body block's own bindings, stored without the use line's steps, as a set stores its
        // values.
        scope* body = make_scope(snippet->scope);
        for (std::size_t i = 0; i < snippet->params.size(); ++i) {
            if (i >= snippet->line->parameters.size()) {
                break;
            }
            definition def{snippet->line->parameters[i],
                           {rebase(arena_, values[i], context.via.size(), {}, nullptr)},
                           {},
                           std::nullopt};
            if (written[i] != nullptr) {
                def.written.push_back(written[i]);
            }
            body->param(snippet->params[i], keep(std::move(def)));
        }
        std::vector<open_item> open = context.open;
        open.emplace_back(snippet);
        blocks.push_back(
            {snippet->block,
             {snippet->text, body,
              with_step(::knobly::step(::knobly::step_kind::use, name, text.place(keyword.span)), context.via),
              std::move(open), context.into, context.nesting}});
        return std::nullopt;
    }

    /// An extension directive's block: only set lines (E5012), bound for the spliced files. Its lines stand at the
    /// extension line's `nesting`: the block is gone after expansion.
    failure extension_block(const std::optional<::knobly::syntax::node>& block, const text_ref& text, block_scope& sc,
                            const std::vector<::knobly::step>& via, std::int64_t nesting,
                            std::map<std::string, const definition*>& forced) {
        if (!block) {
            return std::nullopt;
        }
        scope* own = make_scope(&sc);
        const parsed_text& p = *text.parsed;
        for (const ::knobly::syntax::node& n : block->children()) {
            // Already reported by the parser; the broken line may be a set the files need: the include is unreadable.
            if (n.kind() == ::knobly::node_kind::error) {
                return problem{::knobly::unreadable_reason::syntax, std::nullopt};
            }
            if (n.kind() != ::knobly::node_kind::directive || text.doc == nullptr) {
                continue;
            }
            const anatomy a = anatomy_of(p, n);
            const token_info& name = p.at(a.name);
            if (name.kind != ::knobly::token_kind::AT_WORD ||
                statement_of_keyword(p.text_at(a.name).substr(1)) != ::knobly::statement_kind::set) {
                return at(::knobly::diagnostic_code::extension_block_not_set, text, name.span, via);
            }
            if (failure f =
                    set(a, copy_of(text.doc->statements_by_token.at(n.start()), via), text, *own, via, nesting)) {
                return f;
            }
        }
        forced = own->own();
        return std::nullopt;
    }

    /// An extension directive: the files its specs name, spliced in place.
    failure extension(const std::string& directive, const ::knobly::written::extension& ext, const anatomy& a,
                      const token_info& name, copy_node* copy, place_context& context, std::vector<opened>& blocks) {
        const text_ref& text = context.text;
        edge_node* const edge = binding_->nodes.make<edge_node>(copy);
        binding_->edges.push_back(edge);
        std::vector<expanded_node*> values;
        for (const value_ref& ref : a.values) {
            if (failure f = value(text, ref, *context.scope, context.via, copy, values)) {
                return f;
            }
        }
        if (failure f =
                check_nesting(context.nesting, false, {values.begin(), values.end()}, text, name, context.via)) {
            return f;
        }
        std::map<std::string, const definition*> forced;
        if (failure f = extension_block(a.block, text, *context.scope, context.via, context.nesting, forced)) {
            return f;
        }
        const auto fail = [&](::knobly::diagnostic_code code, std::string detail) {
            return at(code, text, name.span, context.via, std::move(detail));
        };
        std::vector<::knobly::written::expanded_value> handles;
        handles.reserve(values.size());
        for (expanded_node* v : values) {
            handles.push_back(make_handle<::knobly::written::expanded_value>(v));
        }
        const ::knobly::written::extension_use use(handles,
                                                   ::knobly::directive_origin(text.place(name.span), context.via));
        ::knobly::sequence<std::string> given;
        const std::exception_ptr error = ::knobly::detail::catch_exception([&] { given = ext.specs(use); });
        if (error) {
            std::optional<::knobly::located_diagnostic> own;
            if (::knobly::detail::when_caught<::knobly::diagnostic_error>(
                    error, [&](const ::knobly::diagnostic_error& e) { own = e.diagnostic(); })) {
                return problem{::knobly::unreadable_reason::extension, own};
            }
            return fail(::knobly::diagnostic_code::extension_failed,
                        directive + ": " + ::knobly::detail::message_of(error));
        }
        edge->specs.assign(given.begin(), given.end());
        const auto unread = [&](read_need need) {
            binding_->needs[edge] = std::move(need);
            binding_->unread.push_back(edge);
            return fail(::knobly::diagnostic_code::unread_copy, directive);
        };
        std::vector<std::string> found;
        for (const std::string& spec : edge->specs) {
            const auto resolved = graph_->resolved.find({text.resolved_path, spec});
            if (resolved == graph_->resolved.end()) {
                return unread({true, text.resolved_path, edge->specs, {}});
            }
            if (resolved->second.failure) {
                return fail(::knobly::diagnostic_code::include_resolver_failed,
                            spec + ": " + *resolved->second.failure);
            }
            if (resolved->second.paths.empty()) {
                return fail(::knobly::diagnostic_code::include_not_found, spec);
            }
            std::vector<std::string> paths = resolved->second.paths;
            std::sort(paths.begin(), paths.end());  // byte order is code point order (design.md 2.4)
            found.insert(found.end(), paths.begin(), paths.end());
        }
        for (const std::string& path : found) {
            for (const open_item& item : context.open) {
                if (const auto* open = std::get_if<std::string>(&item); open != nullptr && *open == path) {
                    return at(::knobly::diagnostic_code::expansion_cycle, text, name.span, context.via, path);
                }
            }
        }
        if (failure f = check_depth(context.open, text, name, context.via)) {
            return f;
        }
        std::vector<document_node*> files;
        for (const std::string& path : found) {
            if (document_node* doc = graph_->document(path)) {
                files.push_back(doc);
                continue;
            }
            const auto failed = graph_->failed_reads.find(path);
            if (failed == graph_->failed_reads.end()) {
                return unread({false, {}, {}, found});
            }
            return fail(::knobly::diagnostic_code::include_resolver_failed, path + ": " + failed->second);
        }
        edge->targets = found;
        // The step's name is the extension's, without @, as a variable step's is without $; its place the @name.
        const ::knobly::step step(::knobly::step_kind::extension, directive, text.place(name.span));
        splices_.push_back(std::make_unique<splice_scope>(context.scope, std::move(forced)));
        block_scope* const spliced = splices_.back().get();
        for (document_node* file : files) {
            std::vector<open_item> open = context.open;
            open.emplace_back(file->path);
            blocks.push_back({file->parsed.syntax.root(),
                              {document_text(file), spliced, with_step(step, context.via), std::move(open),
                               context.into, context.nesting}});
        }
        return std::nullopt;
    }

    /// $name's values as read here: each with the variable step, then the reading place's steps (and a resolution for
    /// `reference`, its written handle: the token's own value, or a slice's name).
    failure variable(const text_ref& text, std::int64_t token, const scope_view& sc,
                     const std::vector<::knobly::step>& via, copy_node* copy, value_node* reference,
                     std::vector<expanded_node*>& out) {
        const parsed_text& p = *text.parsed;
        const std::string name(p.text_at(token).substr(1));
        std::vector<entry> entries;
        sc.entries(name, entries);
        const auto given = overrides_.find(name);
        const std::vector<const definition*> picked =
            ordered(std::move(entries), given == overrides_.end() ? nullptr : given->second);
        const definition* const winner = picked.empty() ? nullptr : picked.front();
        resolution_node* resolution = nullptr;
        if (copy != nullptr && reference != nullptr && binding_ != nullptr) {
            resolution = binding_->nodes.make<resolution_node>(copy);
            resolution->reference = reference;
            if (winner != nullptr) {
                resolution->winner = winner->variable;
                resolution->values = winner->written;
            }
            for (std::size_t i = 1; i < picked.size(); ++i) {
                resolution->shadowed.push_back(picked[i]->variable);
            }
            binding_->resolutions.push_back(resolution);
            binding_->by_reference[reference].push_back(resolution);
        }
        if (winner == nullptr) {
            return at(::knobly::diagnostic_code::unknown_variable, text, p.at(token).span, via,
                      std::string(p.text_at(token)));
        }
        if (winner->problem) {
            // An override is written in no file: its problem is placed on the $name that used it.
            return problem{::knobly::unreadable_reason::value,
                           ::knobly::located_diagnostic(::knobly::diagnostic_code::non_integer_bound, *winner->problem,
                                                        text.place(p.at(token).span), via)};
        }
        const std::vector<::knobly::step> steps =
            with_step(::knobly::step(::knobly::step_kind::variable, name, text.place(p.at(token).span)), via);
        for (const expanded_node* v : winner->values) {
            out.push_back(rebase(arena_, v, 0, steps, resolution));
        }
        return std::nullopt;
    }

    /// name[bounds]: the name a word, or a variable holding exactly one word (E4007 otherwise); each bound a literal
    /// INTEGER or a variable holding exactly one IntegerText (E4001 otherwise). Read where written.
    failure slice(const text_ref& text, const ::knobly::syntax::node& n, const scope_view& sc,
                  const std::vector<::knobly::step>& via, copy_node* copy, value_node* written,
                  std::vector<expanded_node*>& out) {
        const parsed_text& p = *text.parsed;
        value_node* written_name = written != nullptr && (written->kind == ::knobly::value_kind::slice ||
                                                          written->kind == ::knobly::value_kind::index)
                                       ? written->name
                                       : nullptr;
        std::string name;
        if (failure f = slice_name(text, n.start(), sc, via, copy,
                                   written_name != nullptr && written_name->kind == ::knobly::value_kind::reference
                                       ? written_name
                                       : nullptr,
                                   name)) {
            return f;
        }
        std::vector<std::int64_t> inner;
        for (std::int64_t i = n.start() + 2; i < n.end() - 1; ++i) {
            inner.push_back(i);
        }
        const auto bound_at = [&](std::size_t i, std::optional<std::int64_t>& value) -> failure {
            if (i >= inner.size()) {
                return std::nullopt;
            }
            std::int64_t read = 0;
            if (failure f = bound(text, inner[i], sc, via, copy, read)) {
                return f;
            }
            value = read;
            return std::nullopt;
        };
        const ::knobly::origin origin(text.written(p.span_of(n.start(), n.end())), via);
        std::optional<std::size_t> tilde;
        for (std::size_t i = 0; i < inner.size(); ++i) {
            if (p.is(inner[i], ::knobly::token_kind::TILDE)) {
                tilde = i;
                break;
            }
        }
        expanded_data data;
        data.name = std::move(name);
        if (!tilde) {
            std::optional<std::int64_t> index;
            if (failure f = bound_at(0, index)) {
                return f;
            }
            data.kind = ::knobly::value_kind::index;
            data.index = index.value_or(0);
        } else {
            data.kind = ::knobly::value_kind::slice;
            if (*tilde != 0) {
                if (failure f = bound_at(0, data.start)) {
                    return f;
                }
            }
            if (*tilde + 1 < inner.size()) {
                if (failure f = bound_at(*tilde + 1, data.end)) {
                    return f;
                }
            }
        }
        out.push_back(make_expanded(arena_, std::move(data), origin, written));
        return std::nullopt;
    }

    /// A slice's name: a word's text, or the one word its variable holds, a word that may name a slice (sliceNameText:
    /// a WORD or an AT_WORD); E4007 otherwise, placed as E4001 is.
    failure slice_name(const text_ref& text, std::int64_t token, const scope_view& sc,
                       const std::vector<::knobly::step>& via, copy_node* copy, value_node* reference,
                       std::string& name) {
        const parsed_text& p = *text.parsed;
        if (!p.is(token, ::knobly::token_kind::VARIABLE)) {
            name = std::string(p.text_at(token));
            return std::nullopt;
        }
        std::vector<expanded_node*> values;
        if (failure f = variable(text, token, sc, via, copy, reference, values)) {
            return f;
        }
        const expanded_node* const only = values.empty() ? nullptr : values.front();
        if (values.size() == 1 && only->kind == ::knobly::value_kind::word &&
            parse_entry(only->text, entry_rule::slice_name_text).syntax.diagnostics().empty()) {
            name = only->text;
            return std::nullopt;
        }
        return through_variable(::knobly::diagnostic_code::bad_slice_name, text, token, via, only);
    }

    /// One slice bound's integer: E4001 at a literal beyond the integer range, or for a variable at its value's place
    /// via the variable.
    failure bound(const text_ref& text, std::int64_t token, const scope_view& sc,
                  const std::vector<::knobly::step>& via, copy_node* copy, std::int64_t& read) {
        const parsed_text& p = *text.parsed;
        if (p.is(token, ::knobly::token_kind::INTEGER)) {
            const std::optional<std::int64_t> value = ::knobly::detail::rules::integer_of(p.text_at(token));
            if (!value) {
                return at(::knobly::diagnostic_code::non_integer_bound, text, p.at(token).span, via,
                          std::string(p.text_at(token)));
            }
            read = *value;
            return std::nullopt;
        }
        value_node* const written = value_of(text, token);
        std::vector<expanded_node*> values;
        if (failure f = variable(
                text, token, sc, via, copy,
                written != nullptr && written->kind == ::knobly::value_kind::reference ? written : nullptr, values)) {
            return f;
        }
        const expanded_node* const only = values.empty() ? nullptr : values.front();
        if (values.size() == 1 && only->kind == ::knobly::value_kind::word) {
            if (const std::optional<std::int64_t> value = ::knobly::detail::rules::integer_of(only->text)) {
                read = *value;
                return std::nullopt;
            }
        }
        return through_variable(::knobly::diagnostic_code::non_integer_bound, text, token, via, only);
    }

    /// A slice name's or bound's problem through a variable: at its (first) value's place via the variable, or at the
    /// $name when that value is an override's (written in no file).
    problem through_variable(::knobly::diagnostic_code code, const text_ref& text, std::int64_t token,
                             const std::vector<::knobly::step>& via, const expanded_node* only) const {
        const parsed_text& p = *text.parsed;
        if (only == nullptr) {
            return at(code, text, p.at(token).span, via, std::string(p.text_at(token)));
        }
        const auto place = only->origin.place();
        const auto* file = std::get_if<::knobly::place>(&place);
        if (file == nullptr) {
            return at(code, text, p.at(token).span, via, std::string(p.text_at(token)));
        }
        const ::knobly::sequence<::knobly::step> steps = only->origin.via();
        return located(code, *file, {steps.begin(), steps.end()}, std::string(p.text_at(token)) + " is " + only->text);
    }

    binding_core* binding_;
    arena& arena_;
    graph_core* graph_;
    std::map<std::string, const definition*> overrides_;
    std::deque<std::unique_ptr<scope_view>> scopes_;
    std::deque<std::unique_ptr<splice_scope>> splices_;
    std::deque<definition> definitions_;
    std::deque<snippet_def> snippets_;
    std::size_t count_ = 0;
    bool stopped_ = false;
};

/// An override's values, from its text parsed with the valuesText entry rule (records kept in the graph's arena). Call
/// only with text the check of an override accepted: values without a $name.
inline override_values read_override(graph_core* graph, const std::string& name, const parsed_text& parsed) {
    const text_ref text{nullptr, &parsed, {}, name};
    walk w(nullptr, graph->nodes, graph);
    const scope empty(nullptr);
    override_values out;
    for (const value_ref& ref : values_of(parsed)) {
        if (failure f = w.value(text, ref, empty, {}, nullptr, out.values)) {
            if (f->diagnostic) {
                return {{}, f->diagnostic->message()};
            }
        }
    }
    return out;
}

/// The binding of the graph's current state, its walk run.
inline void derive(binding_core* binding, document_node* root) {
    walk w(binding, binding->nodes, binding->graph);
    w.run(root);
}

}  // namespace written::detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_BIND_HPP
