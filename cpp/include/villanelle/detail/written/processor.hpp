// The processor and load (spec 6.2): sources, extensions, overrides, the first read.
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_WRITTEN_PROCESSOR_HPP
#define VILLANELLE_DETAIL_WRITTEN_PROCESSOR_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

VILLANELLE_API processor::processor(::villanelle::written::processor_options) {
    ::villanelle::detail::not_built("written::processor::processor");
}

VILLANELLE_API ::villanelle::written::document_graph processor::load(std::string_view) const {
    ::villanelle::detail::not_built("written::processor::load");
}

VILLANELLE_API ::villanelle::written::document_graph processor::load(std::string_view,
                                                                     ::villanelle::written::load_options) const {
    ::villanelle::detail::not_built("written::processor::load");
}

VILLANELLE_API bool operator==(const ::villanelle::written::processor&, const ::villanelle::written::processor&) {
    ::villanelle::detail::not_built("operator== of processor");
}

}  // namespace written

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_PROCESSOR_HPP
