// The memory adapters (spec 4.3): memory_source over a shared map, read at every call (never a copy), and
// memory_writer into it, so a save is seen by the next load. Pure: no input or output. Paths resolve through
// detail::io::join, has_glob and glob_match (paths.hpp), the rules file_source shares (frozen-m2.md 3.4).
#ifndef VILLANELLE_DETAIL_IO_MEMORY_HPP
#define VILLANELLE_DETAIL_IO_MEMORY_HPP

#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <villanelle/detail/io/lost_updates.hpp>
#include <villanelle/detail/io/paths.hpp>
#include <villanelle/detail/raise.hpp>
#include <villanelle/villanelle.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace detail::io {

class memory_source final : public ::villanelle::document_source {
public:
    explicit memory_source(std::shared_ptr<const ::villanelle::ordered_map<std::string, std::string>> files)
        : files_(std::move(files)) {}

    /// The joined path when it is a key; for a glob in the last segment, every key in that directory it matches.
    ::villanelle::sequence<std::string> resolve(std::string_view spec,
                                                const ::villanelle::load_context& context) const override {
        const std::string path = join(context.parent_path(), spec);
        if (!has_glob(path)) {
            if (files_->contains(path)) {
                return {path};
            }
            return {};
        }
        const std::string_view directory = directory_of(path);
        const std::string_view pattern = std::string_view(path).substr(directory.size());
        std::vector<std::string> found;
        for (const auto& [key, text] : *files_) {
            if (directory_of(key) == directory && glob_match(pattern, std::string_view(key).substr(directory.size()))) {
                found.push_back(key);
            }
        }
        return found;
    }

    /// @throws std::runtime_error for a path that is not a key (a port's failure: load reports it)
    std::string read(std::string_view resolved_path) const override {
        std::optional<std::string> text = files_->find(std::string(resolved_path));
        if (!text) {
            ::villanelle::detail::raise(std::runtime_error("no such file: " + std::string(resolved_path)));
        }
        return std::move(*text);
    }

private:
    std::shared_ptr<const ::villanelle::ordered_map<std::string, std::string>> files_;
};

class memory_writer final : public ::villanelle::document_writer {
public:
    explicit memory_writer(std::shared_ptr<::villanelle::ordered_map<std::string, std::string>> files)
        : files_(std::move(files)) {}

    /// All or nothing: the one lost-update check first, then every file's text.
    void write(::villanelle::sequence<::villanelle::file_write> files) const override {
        std::vector<std::optional<std::string>> current;
        current.reserve(files.size());
        for (const ::villanelle::file_write& file : files) {
            current.push_back(files_->find(file.resolved_path()));
        }
        ::villanelle::check_lost_updates(files, current);
        for (const ::villanelle::file_write& file : files) {
            files_->insert_or_assign(file.resolved_path(), file.text());
        }
    }

private:
    std::shared_ptr<::villanelle::ordered_map<std::string, std::string>> files_;
};

}  // namespace detail::io

/// @throws villanelle::argument_type_error given no map
VILLANELLE_API std::shared_ptr<::villanelle::document_source> memory_source(
    std::shared_ptr<const ::villanelle::ordered_map<std::string, std::string>> files) {
    if (!files) {
        ::villanelle::detail::raise(::villanelle::argument_type_error(
            ::villanelle::detail::argument_type_message("memory_source", "files", "null")));
    }
    return std::make_shared<::villanelle::detail::io::memory_source>(std::move(files));
}

/// @throws villanelle::argument_type_error given no map
VILLANELLE_API std::shared_ptr<::villanelle::document_writer> memory_writer(
    std::shared_ptr<::villanelle::ordered_map<std::string, std::string>> files) {
    if (!files) {
        ::villanelle::detail::raise(::villanelle::argument_type_error(
            ::villanelle::detail::argument_type_message("memory_writer", "files", "null")));
    }
    return std::make_shared<::villanelle::detail::io::memory_writer>(std::move(files));
}

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_IO_MEMORY_HPP
