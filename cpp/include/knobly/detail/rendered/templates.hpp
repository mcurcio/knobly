// The rendered layer's templates (frozen-m2.md 3.1): <knobly/rendered.hpp> includes this file in both modes. The
// block_traits specialization support/block.hpp reads for the rendered block; its static members are defined with the
// layer (detail/rendered/definitions.hpp, slice R).
#ifndef KNOBLY_DETAIL_RENDERED_TEMPLATES_HPP
#define KNOBLY_DETAIL_RENDERED_TEMPLATES_HPP

#include <optional>
#include <string_view>

#include <knobly/rendered.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace detail {

/// The rendered block's items are rendered directives (a snapshot of one render).
template <>
struct block_traits<::knobly::rendered::directive> {
    using directive = ::knobly::rendered::directive;
    KNOBLY_API static ::knobly::sequence<::knobly::rendered::directive> items(const view& block);
    KNOBLY_API static std::size_t size(const view& block);
    KNOBLY_API static ::knobly::rendered::directive at(const view& block, std::size_t index);
    KNOBLY_API static std::optional<directive> as_directive(const ::knobly::rendered::directive& item,
                                                            std::optional<std::string_view> name);
    KNOBLY_API static std::optional<view> block_of(const ::knobly::rendered::directive& item);
};

}  // namespace detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_RENDERED_TEMPLATES_HPP
