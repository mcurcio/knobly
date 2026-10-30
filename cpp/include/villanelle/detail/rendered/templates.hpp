// The rendered layer's templates (frozen-m2.md 3.1): <villanelle/rendered.hpp> includes this file in both modes. The
// block_traits specialization support/block.hpp reads for the rendered block; its static members are defined with the
// layer (detail/rendered/definitions.hpp, slice R).
#ifndef VILLANELLE_DETAIL_RENDERED_TEMPLATES_HPP
#define VILLANELLE_DETAIL_RENDERED_TEMPLATES_HPP

#include <optional>
#include <string_view>

#include <villanelle/rendered.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

/// The rendered block's items are rendered directives (a snapshot of one render).
template <>
struct block_traits<::villanelle::rendered::directive> {
    using directive = ::villanelle::rendered::directive;
    VILLANELLE_API static ::villanelle::sequence<::villanelle::rendered::directive> items(const view& block);
    VILLANELLE_API static std::optional<directive> as_directive(const ::villanelle::rendered::directive& item,
                                                                std::optional<std::string_view> name);
    VILLANELLE_API static std::optional<view> block_of(const ::villanelle::rendered::directive& item);
};

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_RENDERED_TEMPLATES_HPP
