// The shared layer's diagnostics collector (spec 7.7): the one sink load, value readers and programs report into.
// A handle (const is shallow, design.md 2.3): copies share one list. A port of ts/src/report.ts.
#ifndef VILLANELLE_DETAIL_SHARED_DIAGNOSTICS_HPP
#define VILLANELLE_DETAIL_SHARED_DIAGNOSTICS_HPP

#include <utility>
#include <vector>

#include <villanelle/support/view.hpp>
#include <villanelle/villanelle.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace detail {

/// What a diagnostics handle shows: the list, counted by its views.
struct diagnostics_node : node {
    std::vector<::villanelle::located_diagnostic> items;
};

VILLANELLE_API std::vector<::villanelle::located_diagnostic>& items_of(const view& v) {
    return static_cast<diagnostics_node*>(v.get())->items;
}

}  // namespace detail

VILLANELLE_API diagnostics::diagnostics() : view_(new ::villanelle::detail::diagnostics_node()) {}

VILLANELLE_API diagnostics::diagnostics(::villanelle::sequence<::villanelle::located_diagnostic> initial)
    : diagnostics() {
    for (const ::villanelle::located_diagnostic& item : initial) {
        ::villanelle::detail::items_of(view_).push_back(item);
    }
}

VILLANELLE_API void diagnostics::add(const ::villanelle::located_diagnostic& diagnostic) const {
    ::villanelle::detail::items_of(view_).push_back(diagnostic);
}

VILLANELLE_API std::size_t diagnostics::size() const { return ::villanelle::detail::items_of(view_).size(); }

VILLANELLE_API bool diagnostics::empty() const { return ::villanelle::detail::items_of(view_).empty(); }

/// A snapshot of the list, so an add during a loop never invalidates it.
VILLANELLE_API ::villanelle::sequence<::villanelle::located_diagnostic>::iterator diagnostics::begin() const {
    return ::villanelle::sequence<::villanelle::located_diagnostic>(::villanelle::detail::items_of(view_)).begin();
}

/// The end of the same list as begin(), counted from the snapshot it takes.
VILLANELLE_API ::villanelle::sequence<::villanelle::located_diagnostic>::iterator diagnostics::end() const {
    return ::villanelle::sequence<::villanelle::located_diagnostic>(::villanelle::detail::items_of(view_)).end();
}

VILLANELLE_API bool operator==(const ::villanelle::diagnostics& a, const ::villanelle::diagnostics& b) {
    return a.view_ == b.view_;
}

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_SHARED_DIAGNOSTICS_HPP
