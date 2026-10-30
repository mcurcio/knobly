// The processor and load (spec 6.2; ts/src/written/processor.ts): made once with its document source and
// extensions; load reads a root file and everything it includes into a document graph.
#ifndef VILLANELLE_DETAIL_WRITTEN_PROCESSOR_HPP
#define VILLANELLE_DETAIL_WRITTEN_PROCESSOR_HPP

#include <algorithm>
#include <string>
#include <string_view>
#include <utility>

#include <villanelle/detail/raise.hpp>
#include <villanelle/detail/written/core.hpp>
#include <villanelle/detail/written/host.hpp>
#include <villanelle/detail/written/shape.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

/// @throws villanelle::argument_type_error given no source or a null extension
/// @throws villanelle::misuse_error for an extension whose directive is not a directive name, is reserved (set,
///     snippet, use) or is taken by an earlier one
VILLANELLE_API processor::processor(::villanelle::written::processor_options options)
    : view_(new detail::processor_node()) {
    auto* state = static_cast<detail::processor_node*>(view_.get());
    if (!options.source) {
        ::villanelle::detail::raise(::villanelle::argument_type_error(
            ::villanelle::detail::argument_type_message("processor", "source", "null")));
    }
    state->source = std::move(options.source);
    for (const std::shared_ptr<::villanelle::written::extension>& extension : options.extensions) {
        if (!extension) {
            ::villanelle::detail::raise(::villanelle::argument_type_error(
                ::villanelle::detail::argument_type_message("processor", "extensions", "null")));
        }
        const std::string name = extension->directive();
        detail::check_directive_name(name);
        const bool reserved = std::find(::villanelle::written::reserved.begin(), ::villanelle::written::reserved.end(),
                                        name) != ::villanelle::written::reserved.end();
        const bool taken = std::any_of(state->extensions.begin(), state->extensions.end(),
                                       [&](const auto& entry) { return entry.first == name; });
        if (reserved || taken) {
            ::villanelle::detail::raise(::villanelle::misuse_error("extension directive name taken: " +
                                                                   ::villanelle::detail::quoted_for_message(name)));
        }
        state->extensions.emplace_back(name, extension);
    }
}

VILLANELLE_API ::villanelle::written::document_graph processor::load(std::string_view path) const {
    return load(path, {});
}

/// Each override goes through the check of an override, in order; the first refusal throws. @throws
/// villanelle::read_error when the root file cannot be read
VILLANELLE_API ::villanelle::written::document_graph processor::load(
    std::string_view path, ::villanelle::written::load_options options) const {
    const auto* state = static_cast<const detail::processor_node*>(view_.get());
    auto* core = new detail::graph_core();
    // The handle first: it holds the graph while the load makes views (an extension's values) and if it fails.
    const ::villanelle::written::document_graph graph =
        detail::make_handle<::villanelle::written::document_graph>(core);
    core->source = state->source;
    core->extensions = state->extensions;
    for (const auto& [name, extension] : state->extensions) {
        core->extension_names.insert(name);
    }
    for (const auto& [name, text] : options.overrides) {
        detail::override_values values = detail::check_override(core, name, text.view());
        detail::put_override(core, name, text, std::move(values));
    }
    detail::read_root(core, path);
    return graph;
}

}  // namespace written

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_PROCESSOR_HPP
