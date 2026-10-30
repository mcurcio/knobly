// check_lost_updates (spec 4.2): the one lost-update check every writer calls before it writes. Defined whole in the
// milestone 2 freeze (frozen-m2.md 3.4), because both wave-1 slices' writers call it.
#ifndef VILLANELLE_DETAIL_IO_LOST_UPDATES_HPP
#define VILLANELLE_DETAIL_IO_LOST_UPDATES_HPP

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

#include <villanelle/detail/raise.hpp>
#include <villanelle/villanelle.hpp>

VILLANELLE_NAMESPACE_BEGIN

VILLANELLE_API void check_lost_updates(::villanelle::sequence<::villanelle::file_write> files,
                                       ::villanelle::sequence<std::optional<std::string>> current) {
    if (current.size() != files.size()) {
        ::villanelle::detail::raise(::villanelle::misuse_error("check_lost_updates: " + std::to_string(files.size()) +
                                                               " files but " + std::to_string(current.size()) +
                                                               " current texts"));
    }
    std::vector<std::string> lost;
    for (std::size_t i = 0; i < files.size(); ++i) {
        const ::villanelle::file_write file = files.at(i);
        if (current.at(i).value_or(std::string()) != file.saved_text()) {
            lost.push_back(file.resolved_path());
        }
    }
    if (!lost.empty()) {
        ::villanelle::detail::raise(::villanelle::lost_update_error(std::move(lost)));
    }
}

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_IO_LOST_UPDATES_HPP
