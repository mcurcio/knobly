// The files definitions' entry point: <villanelle/files.hpp> includes it at its end in header-only mode,
// and <villanelle/implementation.hpp> in compiled mode. Every definition here carries VILLANELLE_API (or is a
// template). A document source and a writer over the local filesystem (spec 4.2, 4.3), ports of
// py/src/villanelle/files.py and ts/src/node.ts. Paths resolve through detail::io (the one POSIX join and glob rule,
// shared with memory_source); the filesystem is reached through <cstdio> and <filesystem> only. Failures are read
// from error codes and raised through detail::raise (frozen-m2.md 3.3 rule 7: no throw or try here).
#ifndef VILLANELLE_DETAIL_FILES_DEFINITIONS_HPP
#define VILLANELLE_DETAIL_FILES_DEFINITIONS_HPP

#include <cerrno>
#include <cstddef>
#include <cstdio>
#include <filesystem>
#include <memory>
#include <optional>
#include <random>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>
#include <vector>

#include <villanelle/detail/io/lost_updates.hpp>
#include <villanelle/detail/io/paths.hpp>
#include <villanelle/detail/raise.hpp>
#include <villanelle/files.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace detail::files {

/// Raises the filesystem failure `code` on `path`, as the standard library's own filesystem error.
[[noreturn]] VILLANELLE_API void raise_failure(const char* what, const std::string& path, std::error_code code) {
    ::villanelle::detail::raise(std::filesystem::filesystem_error(what, std::filesystem::path(path), code));
}

/// The error code errno holds now (after a failed <cstdio> call).
VILLANELLE_API std::error_code last_error() noexcept { return {errno, std::generic_category()}; }

/// Whether a failure only says that nothing is at the path: a missing file or directory, or a path through a file.
VILLANELLE_API bool is_absent(std::error_code code) noexcept {
    return code == std::errc::no_such_file_or_directory || code == std::errc::not_a_directory;
}

/// Whether `path` names a regular file (symbolic links followed); false when nothing is there. Other failures raise.
VILLANELLE_API bool is_file(const std::string& path) {
    std::error_code code;
    const std::filesystem::file_status status = std::filesystem::status(std::filesystem::path(path), code);
    if (code && !is_absent(code)) {
        raise_failure("cannot stat", path, code);
    }
    return std::filesystem::is_regular_file(status);
}

/// The bytes of `path`, whole. Nothing there: std::nullopt when `allow_absent`, else it raises, as any other failure.
VILLANELLE_API std::optional<std::string> read_bytes(const std::string& path, bool allow_absent) {
    std::FILE* file = std::fopen(path.c_str(), "rb");
    if (file == nullptr) {
        const std::error_code code = last_error();
        if (allow_absent && is_absent(code)) {
            return std::nullopt;
        }
        raise_failure("cannot open", path, code);
    }
    std::string text;
    char buffer[65536];
    std::size_t got = 0;
    while ((got = std::fread(buffer, 1, sizeof buffer, file)) > 0) {
        text.append(buffer, got);
    }
    const bool failed = std::ferror(file) != 0;
    const std::error_code code = last_error();
    std::fclose(file);
    if (failed) {
        raise_failure("cannot read", path, code);
    }
    return text;
}

class file_source final : public ::villanelle::document_source {
public:
    ::villanelle::sequence<std::string> resolve(std::string_view spec,
                                                const ::villanelle::load_context& context) const override {
        const std::string path = ::villanelle::detail::io::join(context.parent_path(), spec);
        if (!::villanelle::detail::io::has_glob(path)) {
            if (is_file(path)) {
                return {path};
            }
            return {};
        }
        // A glob: list its directory and keep the regular files whose name matches its last segment.
        const std::string directory(::villanelle::detail::io::directory_of(path));
        const std::string_view pattern = std::string_view(path).substr(directory.size());
        std::error_code code;
        std::filesystem::directory_iterator entries(std::filesystem::path(directory.empty() ? "." : directory), code);
        if (code) {
            if (is_absent(code)) {
                return {};
            }
            raise_failure("cannot list", directory, code);
        }
        std::vector<std::string> found;
        for (; entries != std::filesystem::directory_iterator(); entries.increment(code)) {
            const std::string name = entries->path().filename().string();
            if (::villanelle::detail::io::glob_match(pattern, name) && is_file(directory + name)) {
                found.push_back(directory + name);
            }
        }
        if (code) {
            raise_failure("cannot list", directory, code);
        }
        return found;
    }

    std::string read(std::string_view resolved_path) const override {
        return *read_bytes(std::string(resolved_path), false);
    }
};

/// A new, empty file beside `target`, named <target>.<random>.tmp and created exclusively: its path and the open
/// file. A null file when it could not be made (`code` says why).
VILLANELLE_API std::pair<std::string, std::FILE*> create_temporary(const std::string& target, std::error_code& code) {
    static constexpr char digits[] = "0123456789abcdef";
    std::random_device random;
    for (int attempt = 0; attempt < 100; ++attempt) {
        std::string path = target + '.';
        for (unsigned bits = random(), i = 0; i < 8; ++i, bits >>= 4U) {
            path += digits[bits & 0xFU];
        }
        path += ".tmp";
        std::FILE* file = std::fopen(path.c_str(), "wbx");
        if (file != nullptr) {
            return {std::move(path), file};
        }
        code = last_error();
        if (code != std::errc::file_exists) {
            break;
        }
    }
    return {std::string(), nullptr};
}

class file_writer final : public ::villanelle::document_writer {
public:
    void write(::villanelle::sequence<::villanelle::file_write> files) const override {
        std::vector<std::optional<std::string>> current;
        current.reserve(files.size());
        for (const ::villanelle::file_write& file : files) {
            current.push_back(read_bytes(file.resolved_path(), true));
        }
        ::villanelle::check_lost_updates(files, std::move(current));

        // Stage every file; on the first failure remove what was staged and raise, with nothing replaced.
        std::vector<std::pair<std::string, std::string>> staged;  // (temporary, target)
        for (const ::villanelle::file_write& file : files) {
            const std::string target = file.resolved_path();
            std::error_code code;
            auto [temporary, out] = create_temporary(target, code);
            if (out == nullptr) {
                remove_from(staged, 0);
                raise_failure("cannot stage", target, code);
            }
            staged.emplace_back(temporary, target);
            const std::string text = file.text();
            const bool written = std::fwrite(text.data(), 1, text.size(), out) == text.size();
            code = last_error();
            const bool closed = std::fclose(out) == 0;
            if (written && !closed) {
                code = last_error();
            }
            if (!written || !closed) {
                remove_from(staged, 0);
                raise_failure("cannot stage", target, code);
            }
        }
        // Rename each over its target in batch order; a failure here can leave earlier files replaced.
        for (std::size_t i = 0; i < staged.size(); ++i) {
            if (std::rename(staged[i].first.c_str(), staged[i].second.c_str()) != 0) {
                const std::error_code code = last_error();
                remove_from(staged, i);
                raise_failure("cannot replace", staged[i].second, code);
            }
        }
    }

private:
    static void remove_from(const std::vector<std::pair<std::string, std::string>>& staged, std::size_t first) {
        for (std::size_t i = first; i < staged.size(); ++i) {
            std::remove(staged[i].first.c_str());
        }
    }
};

}  // namespace detail::files

namespace files {

VILLANELLE_API std::shared_ptr<::villanelle::document_source> file_source() {
    return std::make_shared<::villanelle::detail::files::file_source>();
}

VILLANELLE_API std::shared_ptr<::villanelle::document_writer> file_writer() {
    return std::make_shared<::villanelle::detail::files::file_writer>();
}

}  // namespace files

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_FILES_DEFINITIONS_HPP
