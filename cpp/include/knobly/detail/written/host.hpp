// The document graph's own work (ts/src/written/{graph,read,override,expansion}.ts): the cached binding, the read
// loop, the check of an override, the expansion and save. Everything derived (copies, edges, variables,
// resolutions, diagnostics, the expansion) comes from the binding, cached per graph version; every edit, set_override
// and read bumps the version. Package-internal.
#ifndef KNOBLY_DETAIL_WRITTEN_HOST_HPP
#define KNOBLY_DETAIL_WRITTEN_HOST_HPP

#include <algorithm>
#include <cstddef>
#include <exception>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <knobly/detail/raise.hpp>
#include <knobly/detail/written/bind.hpp>
#include <knobly/detail/written/core.hpp>
#include <knobly/detail/written/edits.hpp>
#include <knobly/detail/written/entry.hpp>
#include <knobly/detail/written/shape.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace written::detail {

/// Gives back a binding's hold unless dismissed (a walk that ends in an exception frees what it made).
struct binding_hold {
    binding_core* held;
    ~binding_hold() {
        if (held != nullptr && held->count.fetch_sub(1, std::memory_order_acq_rel) == 1) {
            delete held;
        }
    }
};

/// The binding of the graph's current version (made when the version moved on).
inline binding_core* binding_of(graph_core* graph) {
    if (graph->binding != nullptr && graph->binding_version == graph->version) {
        return graph->binding;
    }
    auto* made = new binding_core(graph);
    made->count.fetch_add(1, std::memory_order_relaxed);  // the graph's hold, taken before any view is made
    binding_hold hold{made};
    derive(made, graph->documents.front());
    hold.held = nullptr;
    graph->drop_binding();
    graph->binding = made;
    graph->binding_version = graph->version;
    return made;
}

/// Each document's syntax diagnostics (documents in order, located), then the walk's.
inline const std::vector<::knobly::located_diagnostic>& diagnostics_of(graph_core* graph) {
    binding_core* binding = binding_of(graph);
    if (!binding->all_diagnostics) {
        std::vector<::knobly::located_diagnostic> all;
        for (const document_node* doc : graph->documents) {
            for (const ::knobly::diagnostic& d : doc->parsed.syntax.diagnostics()) {
                all.emplace_back(d.code(), d.message(), ::knobly::place(doc->path, d.span()),
                                 ::knobly::sequence<::knobly::step>());
            }
        }
        all.insert(all.end(), binding->diagnostics.begin(), binding->diagnostics.end());
        binding->all_diagnostics = std::move(all);
    }
    return *binding->all_diagnostics;
}

// ---- the expansion (expansion.ts)

/// The directive and unreadable expansions of `top` into `top_block` and `top_unreadable`. A loop over the blocks
/// still to fill, not a recursion: the expanded tree may be max_expanded_nesting deep (spec 2.5). Each block is filled
/// by one task, so each list keeps its written order.
inline void fill(binding_core* binding, const std::vector<bound_item>& top,
                 std::vector<directive_expansion_node*>& top_block, std::vector<unreadable_node*>& top_unreadable) {
    struct task {
        const std::vector<bound_item>* items;
        std::vector<directive_expansion_node*>* block;
        std::vector<unreadable_node*>* unreadable;
    };
    std::vector<task> tasks{{&top, &top_block, &top_unreadable}};
    while (!tasks.empty()) {
        const task next = tasks.back();
        tasks.pop_back();
        for (const bound_item& item : *next.items) {
            statement_node* const statement = item.copy->statement;
            const document_node* doc = statement->doc;
            const parsed_text& p = doc->parsed;
            if (!item.directive) {
                const ::knobly::place place(doc->path, p.span_of(statement->tree.start(), statement->tree.end()));
                next.unreadable->push_back(binding->nodes.make<unreadable_node>(
                    statement, item.reason, ::knobly::directive_origin(place, item.copy->via)));
                continue;
            }
            directive_expansion_node* const made = binding->nodes.make<directive_expansion_node>(
                statement, ::knobly::directive_origin(::knobly::place(doc->path, p.at(statement->tree.start()).span),
                                                      item.copy->via));
            const auto found = binding->expanded.find(item.copy);
            for (value_node* v : statement->values) {
                if (found == binding->expanded.end()) {
                    break;
                }
                const auto values = found->second.find(v);
                if (values != found->second.end()) {
                    made->values.insert(made->values.end(), values->second.begin(), values->second.end());
                }
            }
            if (item.has_children) {
                made->block = binding->nodes.make<expansion_block_node>();
                tasks.push_back({&item.children, &made->block->items, &made->unreadable});
            }
            next.block->push_back(made);
        }
    }
}

/// graph.expand() (spec 6.10): the binding's walk as public snapshots, with the graph's one diagnostics list.
inline expansion_node* expansion_of(graph_core* graph) {
    const std::vector<::knobly::located_diagnostic>& diagnostics = diagnostics_of(graph);
    binding_core* binding = graph->binding;
    if (binding->expansion == nullptr) {
        expansion_node* made = binding->nodes.make<expansion_node>();
        made->block = binding->nodes.make<expansion_block_node>();
        made->diagnostics = diagnostics;
        fill(binding, binding->items, made->block->items, made->unreadable);
        binding->expansion = made;
    }
    return binding->expansion;
}

// ---- the check of an override (override.ts): one check, one home, for load and set_override

/// Checks one override and reads its values: the name (a misuse error unless it is a variable name), then the text
/// with the valuesText entry rule (its diagnostic); else E2001 at a $name, or at 0:0 when it holds no value. Every
/// diagnostic is located in the text.
inline override_values check_override(graph_core* graph, std::string_view name, std::string_view text) {
    check_variable_name(name);
    const parsed_text parsed = parse_entry(text, entry_rule::values_text);
    if (!parsed.syntax.diagnostics().empty()) {
        ::knobly::detail::raise(::knobly::bad_text_error(parsed.syntax.diagnostics()));
    }
    const token_info* first_value = nullptr;
    const token_info* variable = nullptr;
    for (const token_info& token : parsed.tokens) {
        if (token.kind == ::knobly::token_kind::SPACE || token.kind == ::knobly::token_kind::NEWLINE ||
            token.kind == ::knobly::token_kind::COMMENT) {
            continue;
        }
        if (first_value == nullptr) {
            first_value = &token;
        }
        if (variable == nullptr && token.kind == ::knobly::token_kind::VARIABLE) {
            variable = &token;
        }
    }
    if (first_value == nullptr || variable != nullptr) {
        const auto code = ::knobly::diagnostic_code::unexpected_token;
        const ::knobly::source_position position =
            variable != nullptr ? variable->span.start() : ::knobly::source_position(0, 0, 0);
        ::knobly::detail::raise(::knobly::bad_text_error(
            {::knobly::diagnostic(code, ::knobly::describe(code).message, {position, position})}));
    }
    return read_override(graph, std::string(name), parsed);
}

/// A changed name keeps its place in overrides(); a new one (or one removed before) goes at the end.
inline void put_override(graph_core* graph, const std::string& name, ::knobly::config_text text,
                         override_values values) {
    graph->override_texts.insert_or_assign(name, std::move(text));
    graph->overrides[name] = std::move(values);
    if (graph->override_variables.count(name) == 0) {
        variable_node* made = graph->nodes.make<variable_node>(::knobly::variable_kind::override);
        made->name = name;
        made->graph = graph;
        graph->override_variables.emplace(name, made);
    }
}

// ---- the read loop (read.ts)

/// Records one read: the document made from its text, or the failure.
inline document_node* record_read(graph_core* graph, const std::string& path, std::optional<std::string> text,
                                  std::string failure) {
    ++graph->version;
    if (!text) {
        graph->failed_reads[path] = std::move(failure);
        return nullptr;
    }
    document_node* doc = make_document(graph, path, std::move(*text));
    graph->documents.push_back(doc);
    return doc;
}

/// Resolves and reads what the binding names as unread, until nothing new is named: the first unread edge in walk
/// order each time, so files are read depth first, each path once, and a failure is kept, never retried. Returns the
/// paths read, in read order.
inline std::vector<std::string> read_unread(graph_core* graph) {
    std::vector<std::string> read;
    for (;;) {
        binding_core* binding = binding_of(graph);
        if (binding->unread.empty()) {
            return read;
        }
        const read_need need = binding->needs.at(binding->unread.front());
        if (need.resolve) {
            for (const std::string& spec : need.specs) {
                if (graph->resolved.count({need.parent_path, spec}) != 0) {
                    continue;
                }
                ledger_entry entry;
                ::knobly::sequence<std::string> paths;
                const std::exception_ptr error = ::knobly::detail::catch_exception(
                    [&] { paths = graph->source->resolve(spec, ::knobly::load_context(need.parent_path)); });
                if (error) {
                    entry.failure = ::knobly::detail::message_of(error);
                } else {
                    entry.paths.assign(paths.begin(), paths.end());
                }
                const bool stop = entry.failure.has_value() || entry.paths.empty();
                graph->resolved[{need.parent_path, spec}] = std::move(entry);
                ++graph->version;
                // Expansion stops at the first spec that fails: the later ones are not resolved.
                if (stop) {
                    break;
                }
            }
            continue;
        }
        for (const std::string& path : need.paths) {
            if (graph->document(path) != nullptr || graph->failed_reads.count(path) != 0) {
                continue;
            }
            std::string text;
            const std::exception_ptr error =
                ::knobly::detail::catch_exception([&] { text = graph->source->read(path); });
            if (error) {
                record_read(graph, path, std::nullopt, ::knobly::detail::message_of(error));
                break;
            }
            record_read(graph, path, std::move(text), {});
            read.push_back(path);
        }
    }
}

/// Reads the root file at `path` (resolved through the source, as an included file's spec is) into an empty graph,
/// then every file its extension lines name. @throws read_error, paths [path], when the source cannot resolve it to
/// exactly one file, or fails resolving or reading it (that failure nested)
inline void read_root(graph_core* graph, std::string_view path) {
    const std::string root(path);
    const auto fail = [&](const std::string& reason) {
        return ::knobly::read_error("cannot read the root file " + root + ": " + reason,
                                    ::knobly::sequence<std::string>{root});
    };
    ::knobly::sequence<std::string> paths;
    std::exception_ptr error = ::knobly::detail::catch_exception(
        [&] { paths = graph->source->resolve(root, ::knobly::load_context(std::string())); });
    if (error) {
        ::knobly::detail::raise_nested(fail(::knobly::detail::message_of(error)), error);
    }
    if (paths.size() != 1) {
        ::knobly::detail::raise(fail(paths.empty() ? std::string("the source resolved no file")
                                                   : "the source resolved " + std::to_string(paths.size()) + " files"));
    }
    const std::string resolved = paths.front();
    std::string text;
    error = ::knobly::detail::catch_exception([&] { text = graph->source->read(resolved); });
    if (error) {
        ::knobly::detail::raise_nested(fail(::knobly::detail::message_of(error)), error);
    }
    record_read(graph, resolved, std::move(text), {});
    read_unread(graph);
}

// ---- save

/// Hands every changed document to the writer in one batch; their saved text moves only when it returns. A lost
/// update passes through unchanged; any other failure of the writer is a save error with it nested.
inline std::vector<std::string> save(graph_core* graph, const ::knobly::document_writer& writer) {
    std::vector<::knobly::file_write> files;
    std::vector<document_node*> changed;
    for (document_node* doc : graph->documents) {
        if (doc->parsed.text != doc->saved) {
            files.emplace_back(doc->path, doc->parsed.text, doc->saved);
            changed.push_back(doc);
        }
    }
    if (files.empty()) {
        return {};
    }
    std::vector<std::string> paths;
    paths.reserve(files.size());
    for (const ::knobly::file_write& file : files) {
        paths.push_back(file.resolved_path());
    }
    const ::knobly::sequence<::knobly::file_write> batch(files);
    const std::exception_ptr error = ::knobly::detail::catch_exception([&] { writer.write(batch); });
    if (error) {
        if (::knobly::detail::when_caught<::knobly::lost_update_error>(error, [](const auto&) {})) {
            ::knobly::detail::rethrow(error);
        }
        ::knobly::detail::raise_nested(
            ::knobly::save_error("the writer rejected: " + ::knobly::detail::message_of(error), paths), error);
    }
    for (std::size_t i = 0; i < changed.size(); ++i) {
        changed[i]->saved = files[i].text();
    }
    return paths;
}

}  // namespace written::detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_HOST_HPP
