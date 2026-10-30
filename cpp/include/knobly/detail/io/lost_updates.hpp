// check_lost_updates (spec 4.2): the one lost-update check every writer calls before it writes. Defined whole in the
// milestone 2 freeze (frozen-m2.md 3.4), because both wave-1 slices' writers call it.
#ifndef KNOBLY_DETAIL_IO_LOST_UPDATES_HPP
#define KNOBLY_DETAIL_IO_LOST_UPDATES_HPP

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

#include <knobly/detail/raise.hpp>
#include <knobly/knobly.hpp>

KNOBLY_NAMESPACE_BEGIN

KNOBLY_API void check_lost_updates(::knobly::sequence<::knobly::file_write> files,
                                   ::knobly::sequence<std::optional<std::string>> current) {
    if (current.size() != files.size()) {
        ::knobly::detail::raise(::knobly::misuse_error("check_lost_updates: " + std::to_string(files.size()) +
                                                       " files but " + std::to_string(current.size()) +
                                                       " current texts"));
    }
    std::vector<std::string> lost;
    for (std::size_t i = 0; i < files.size(); ++i) {
        const ::knobly::file_write file = files.at(i);
        if (current.at(i).value_or(std::string()) != file.saved_text()) {
            lost.push_back(file.resolved_path());
        }
    }
    if (!lost.empty()) {
        ::knobly::detail::raise(::knobly::lost_update_error(std::move(lost)));
    }
}

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_IO_LOST_UPDATES_HPP
