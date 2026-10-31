// The shared layer's diagnostics collector (spec 7.7): the one sink load, value readers and programs report into.
// A handle (const is shallow, design.md 2.3): copies share one list. A port of ts/src/report.ts. Also each
// diagnostic's severity (spec 2.3), worked out from its code, a port of ts/src/diagnostics.ts's severityOf.
#ifndef KNOBLY_DETAIL_SHARED_DIAGNOSTICS_HPP
#define KNOBLY_DETAIL_SHARED_DIAGNOSTICS_HPP

#include <utility>
#include <variant>
#include <vector>

#include <knobly/codes.hpp>
#include <knobly/knobly.hpp>
#include <knobly/support/view.hpp>

KNOBLY_NAMESPACE_BEGIN

/// A knobly code's severity is the registry's (its letter's).
KNOBLY_API ::knobly::severity diagnostic::severity() const noexcept { return facts_of(code()).severity; }

/// A knobly code's severity is the registry's; a program's own code is an error.
KNOBLY_API ::knobly::severity located_diagnostic::severity() const noexcept {
    const auto* own = std::get_if<::knobly::diagnostic_code>(&code_);
    return own != nullptr ? facts_of(*own).severity : ::knobly::severity::error;
}

namespace detail {

/// What a diagnostics handle shows: the list, counted by its views.
struct diagnostics_node : node {
    std::vector<::knobly::located_diagnostic> items;
};

KNOBLY_API std::vector<::knobly::located_diagnostic>& items_of(const view& v) {
    return static_cast<diagnostics_node*>(v.get())->items;
}

}  // namespace detail

KNOBLY_API diagnostics::diagnostics() : view_(new ::knobly::detail::diagnostics_node()) {}

KNOBLY_API diagnostics::diagnostics(::knobly::sequence<::knobly::located_diagnostic> initial) : diagnostics() {
    for (const ::knobly::located_diagnostic& item : initial) {
        ::knobly::detail::items_of(view_).push_back(item);
    }
}

KNOBLY_API void diagnostics::add(const ::knobly::located_diagnostic& diagnostic) const {
    ::knobly::detail::items_of(view_).push_back(diagnostic);
}

KNOBLY_API std::size_t diagnostics::size() const { return ::knobly::detail::items_of(view_).size(); }

KNOBLY_API bool diagnostics::empty() const { return ::knobly::detail::items_of(view_).empty(); }

/// One snapshot of the list, which the iterator holds, so an add during a loop never invalidates it.
KNOBLY_API ::knobly::sequence<::knobly::located_diagnostic>::iterator diagnostics::begin() const {
    return ::knobly::sequence<::knobly::located_diagnostic>(::knobly::detail::items_of(view_)).begin();
}

/// An end of every snapshot: it holds none, so a loop that calls end() each time copies nothing.
KNOBLY_API ::knobly::sequence<::knobly::located_diagnostic>::iterator diagnostics::end() const { return {}; }

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_SHARED_DIAGNOSTICS_HPP
