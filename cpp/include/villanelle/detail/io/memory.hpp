// The memory adapters (spec 4.3): memory_source over a shared map, memory_writer into it.
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_IO_MEMORY_HPP
#define VILLANELLE_DETAIL_IO_MEMORY_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/villanelle.hpp>

VILLANELLE_NAMESPACE_BEGIN

VILLANELLE_API std::shared_ptr<::villanelle::document_source> memory_source(
    std::shared_ptr<const ::villanelle::ordered_map<std::string, std::string>>) {
    ::villanelle::detail::not_built("memory_source");
}

VILLANELLE_API std::shared_ptr<::villanelle::document_writer> memory_writer(
    std::shared_ptr<::villanelle::ordered_map<std::string, std::string>>) {
    ::villanelle::detail::not_built("memory_writer");
}

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_IO_MEMORY_HPP
