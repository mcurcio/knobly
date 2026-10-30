// The files definitions' entry point: <villanelle/files.hpp> includes it at its end in header-only mode,
// and <villanelle/implementation.hpp> in compiled mode. Every definition here carries VILLANELLE_API (or is a
// template). STUBS (frozen-m2.md): each body is not_built until slice F defines it.
#ifndef VILLANELLE_DETAIL_FILES_DEFINITIONS_HPP
#define VILLANELLE_DETAIL_FILES_DEFINITIONS_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/files.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace files {

VILLANELLE_API std::shared_ptr<::villanelle::document_source> file_source() {
    ::villanelle::detail::not_built("files::file_source");
}

VILLANELLE_API std::shared_ptr<::villanelle::document_writer> file_writer() {
    ::villanelle::detail::not_built("files::file_writer");
}

}  // namespace files

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_FILES_DEFINITIONS_HPP
