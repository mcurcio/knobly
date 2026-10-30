// format_diagnostic (spec 7.7): a located diagnostic as text, with source lines when a graph is given.
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_WRITTEN_FORMAT_HPP
#define VILLANELLE_DETAIL_WRITTEN_FORMAT_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

VILLANELLE_API std::string format_diagnostic(const ::villanelle::located_diagnostic&) {
    ::villanelle::detail::not_built("written::format_diagnostic");
}

VILLANELLE_API std::string format_diagnostic(const ::villanelle::located_diagnostic&,
                                             const ::villanelle::written::document_graph&) {
    ::villanelle::detail::not_built("written::format_diagnostic");
}

}  // namespace written

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_FORMAT_HPP
