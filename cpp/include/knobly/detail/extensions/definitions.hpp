// The extensions definitions' entry point: <villanelle/extensions.hpp> includes it at its end in header-only mode,
// and <villanelle/implementation.hpp> in compiled mode. Every definition here carries VILLANELLE_API (or is a
// template). The first-party include extension (spec 5.1), a port of ts/src/written/include.ts, built on the public
// API and codes.hpp only, as a program's own extension would be.
#ifndef VILLANELLE_DETAIL_EXTENSIONS_DEFINITIONS_HPP
#define VILLANELLE_DETAIL_EXTENSIONS_DEFINITIONS_HPP

#include <cstddef>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#include <villanelle/codes.hpp>
#include <villanelle/detail/raise.hpp>
#include <villanelle/errors.hpp>
#include <villanelle/extensions.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace detail::extensions {

/// Raises E3005 at a place: the code's message, with `detail` after it when given.
[[noreturn]] VILLANELLE_API void raise_bad_path(::villanelle::place place,
                                                ::villanelle::sequence<::villanelle::step> via,
                                                const std::optional<std::string>& detail) {
    constexpr ::villanelle::diagnostic_code code = ::villanelle::diagnostic_code::include_bad_path;
    std::string message = detail ? ::villanelle::describe(code, *detail).message : ::villanelle::describe(code).message;
    ::villanelle::detail::raise(::villanelle::diagnostic_error(
        ::villanelle::located_diagnostic(code, std::move(message), std::move(place), std::move(via))));
}

/// Raises E3005 on a value (spec 2.2): its file place and steps; a value written in an override is placed on the
/// $name that used it (its first step), with the steps after that one.
[[noreturn]] VILLANELLE_API void raise_bad_value(const ::villanelle::written::expanded_value& value) {
    const ::villanelle::origin origin = value.origin();
    const ::villanelle::sequence<::villanelle::step> via = origin.via();
    const std::variant<::villanelle::place, ::villanelle::override> where = origin.place();
    if (const auto* place = std::get_if<::villanelle::place>(&where)) {
        raise_bad_path(*place, via, value.text());
    }
    // An override always has its variable step first (the expansion that read it); at() raises when it has none.
    std::vector<::villanelle::step> rest;
    for (std::size_t i = 1; i < via.size(); ++i) {
        rest.push_back(via.at(i));
    }
    raise_bad_path(via.at(0).place(), std::move(rest), value.text());
}

class include final : public ::villanelle::written::extension {
public:
    std::string directive() const override { return "include"; }

    ::villanelle::sequence<std::string> specs(const ::villanelle::written::extension_use& use) const override {
        const ::villanelle::sequence<::villanelle::written::expanded_value> values = use.values();
        if (values.empty()) {
            const ::villanelle::directive_origin origin = use.origin();
            raise_bad_path(origin.place(), origin.via(), std::nullopt);
        }
        const ::villanelle::written::expanded_value path = values.at(0);
        if (path.kind() != ::villanelle::value_kind::string) {
            raise_bad_value(path);
        }
        if (values.size() > 1) {
            raise_bad_value(values.at(1));
        }
        return {path.string()};
    }
};

}  // namespace detail::extensions

namespace extensions {

VILLANELLE_API std::shared_ptr<::villanelle::written::extension> include() {
    return std::make_shared<::villanelle::detail::extensions::include>();
}

}  // namespace extensions

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_EXTENSIONS_DEFINITIONS_HPP
