// The path and glob rules every document source shares (spec 4.1, 4.3): memory_source (slice W) and file_source
// (slice F) both resolve through these, so the rules have one home. Defined whole in the milestone 2 freeze
// (frozen-m2.md 3.4), because both wave-1 slices call them. Paths are UTF-8 text with '/' separators.
#ifndef VILLANELLE_DETAIL_IO_PATHS_HPP
#define VILLANELLE_DETAIL_IO_PATHS_HPP

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

#include <villanelle/detail/text_in.hpp>
#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail::io {

/// Everything up to and including the last '/'; empty for a bare name.
VILLANELLE_API std::string_view directory_of(std::string_view path) noexcept {
    const std::size_t slash = path.rfind('/');
    return slash == std::string_view::npos ? std::string_view() : path.substr(0, slash + 1);
}

/// POSIX rules: empty and "." segments dropped, each ".." removes the segment before it when there is one (and is
/// kept otherwise), a leading '/' kept.
VILLANELLE_API std::string normalize(std::string_view path) {
    std::vector<std::string_view> out;
    std::size_t at = 0;
    while (at <= path.size()) {
        std::size_t end = path.find('/', at);
        if (end == std::string_view::npos) {
            end = path.size();
        }
        const std::string_view segment = path.substr(at, end - at);
        if (segment == ".." && !out.empty() && out.back() != "..") {
            out.pop_back();
        } else if (!segment.empty() && segment != ".") {
            out.push_back(segment);
        }
        at = end + 1;
    }
    std::string joined = !path.empty() && path.front() == '/' ? "/" : "";
    for (std::size_t i = 0; i < out.size(); ++i) {
        if (i > 0) {
            joined += '/';
        }
        joined += out[i];
    }
    return joined;
}

/// A spec resolved against the file that names it (spec 4.3, memory source): a leading '/' taken as is, else joined
/// to the directory of parent_path (empty when the root path itself is resolved); then normalized.
VILLANELLE_API std::string join(std::string_view parent_path, std::string_view spec) {
    if (!spec.empty() && spec.front() == '/') {
        return normalize(spec);
    }
    std::string joined(directory_of(parent_path));
    joined += spec;
    return normalize(joined);
}

/// Whether a spec is a glob: it holds '*' or '?' (spec 4.3).
VILLANELLE_API bool has_glob(std::string_view spec) noexcept {
    return spec.find_first_of("*?") != std::string_view::npos;
}

/// Whether a file name matches a glob's last segment: '*' any run of code points (empty included), '?' exactly one,
/// every other character itself; nothing escapes. Bytes that do not decode match only themselves, byte by byte.
VILLANELLE_API bool glob_match(std::string_view pattern, std::string_view name) {
    std::size_t p = 0;
    std::size_t n = 0;
    std::size_t star = std::string_view::npos;  // the pattern index after the last '*'
    std::size_t resume = 0;                     // the name index that '*' is retried from
    const auto step = [](std::string_view text, std::size_t at) {
        char32_t cp = 0;
        const std::size_t length = decode_utf8(text, at, cp);
        return length == 0 ? std::size_t{1} : length;
    };
    while (n < name.size()) {
        if (p < pattern.size() && pattern[p] == '*') {
            star = ++p;
            resume = n;
        } else if (p < pattern.size() && pattern[p] == '?') {
            ++p;
            n += step(name, n);
        } else if (p < pattern.size()) {
            const std::size_t length = step(pattern, p);
            if (pattern.substr(p, length) == name.substr(n, length)) {
                p += length;
                n += length;
            } else if (star != std::string_view::npos) {
                p = star;
                resume += step(name, resume);
                n = resume;
            } else {
                return false;
            }
        } else if (star != std::string_view::npos) {
            p = star;
            resume += step(name, resume);
            n = resume;
        } else {
            return false;
        }
    }
    while (p < pattern.size() && pattern[p] == '*') {
        ++p;
    }
    return p == pattern.size();
}

}  // namespace detail::io
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_IO_PATHS_HPP
