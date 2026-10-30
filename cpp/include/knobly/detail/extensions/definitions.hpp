// The extensions definitions' entry point: <knobly/extensions.hpp> includes it at its end in header-only mode,
// and <knobly/implementation.hpp> in compiled mode. Every definition here carries KNOBLY_API (or is a
// template). The first-party include extension (spec 5.1), a port of ts/src/written/include.ts, built on the public
// API and codes.hpp only, as a program's own extension would be.
#ifndef KNOBLY_DETAIL_EXTENSIONS_DEFINITIONS_HPP
#define KNOBLY_DETAIL_EXTENSIONS_DEFINITIONS_HPP

#include <cstddef>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#include <knobly/codes.hpp>
#include <knobly/detail/raise.hpp>
#include <knobly/errors.hpp>
#include <knobly/extensions.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace detail::extensions {

/// Raises E3005 at a place: the code's message, with `detail` after it when given.
[[noreturn]] KNOBLY_API void raise_bad_path(::knobly::place place, ::knobly::sequence<::knobly::step> via,
                                            const std::optional<std::string>& detail) {
    constexpr ::knobly::diagnostic_code code = ::knobly::diagnostic_code::include_bad_path;
    std::string message = detail ? ::knobly::describe(code, *detail).message : ::knobly::describe(code).message;
    ::knobly::detail::raise(::knobly::diagnostic_error(
        ::knobly::located_diagnostic(code, std::move(message), std::move(place), std::move(via))));
}

/// Raises E3005 on a value (spec 2.2): its file place and steps; a value written in an override is placed on the
/// $name that used it (its first step), with the steps after that one.
[[noreturn]] KNOBLY_API void raise_bad_value(const ::knobly::written::expanded_value& value) {
    const ::knobly::origin origin = value.origin();
    const ::knobly::sequence<::knobly::step> via = origin.via();
    const std::variant<::knobly::place, ::knobly::override> where = origin.place();
    if (const auto* place = std::get_if<::knobly::place>(&where)) {
        raise_bad_path(*place, via, value.text());
    }
    // An override always has its variable step first (the expansion that read it); at() raises when it has none.
    std::vector<::knobly::step> rest;
    for (std::size_t i = 1; i < via.size(); ++i) {
        rest.push_back(via.at(i));
    }
    raise_bad_path(via.at(0).place(), std::move(rest), value.text());
}

class include final : public ::knobly::written::extension {
public:
    std::string directive() const override { return "include"; }

    ::knobly::sequence<std::string> specs(const ::knobly::written::extension_use& use) const override {
        const ::knobly::sequence<::knobly::written::expanded_value> values = use.values();
        if (values.empty()) {
            const ::knobly::directive_origin origin = use.origin();
            raise_bad_path(origin.place(), origin.via(), std::nullopt);
        }
        const ::knobly::written::expanded_value path = values.at(0);
        if (path.kind() != ::knobly::value_kind::string) {
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

KNOBLY_API std::shared_ptr<::knobly::written::extension> include() {
    return std::make_shared<::knobly::detail::extensions::include>();
}

}  // namespace extensions

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_EXTENSIONS_DEFINITIONS_HPP
