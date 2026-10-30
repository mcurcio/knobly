// files::file_source() and files::file_writer() (spec 4.2, 4.3) against the real filesystem, in a fresh directory
// under the build tree (the test's working directory).
#include <villanelle/files.hpp>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <memory>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

#include <catch2/catch_test_macros.hpp>

namespace vl = villanelle;
namespace fs = std::filesystem;

namespace {

/// A fresh directory for one test case, removed again at its end.
class scratch {
public:
    explicit scratch(const std::string& name) : root_("unit_files_" + name) {
        fs::remove_all(root_);
        fs::create_directories(root_);
    }
    scratch(const scratch&) = delete;
    scratch& operator=(const scratch&) = delete;
    ~scratch() {
        std::error_code ignored;
        fs::remove_all(root_, ignored);
    }
    /// The path of `relative` inside the scratch directory, with '/' separators.
    std::string path(const std::string& relative) const { return (root_ / relative).generic_string(); }
    void write(const std::string& relative, const std::string& text) const {
        fs::create_directories(fs::path(path(relative)).parent_path());
        std::ofstream(path(relative), std::ios::binary) << text;
    }
    std::string read(const std::string& relative) const {
        std::ifstream in(path(relative), std::ios::binary);
        std::ostringstream text;
        text << in.rdbuf();
        return text.str();
    }
    /// Every name directly in `relative`, sorted.
    std::vector<std::string> names(const std::string& relative) const {
        std::vector<std::string> out;
        for (const fs::directory_entry& entry : fs::directory_iterator(path(relative))) {
            out.push_back(entry.path().filename().string());
        }
        std::sort(out.begin(), out.end());
        return out;
    }

private:
    fs::path root_;
};

std::vector<std::string> resolve(const std::string& spec, const std::string& parent) {
    const vl::sequence<std::string> found = vl::files::file_source()->resolve(spec, vl::load_context(parent));
    std::vector<std::string> out(found.begin(), found.end());
    std::sort(out.begin(), out.end());
    return out;
}

using strings = std::vector<std::string>;

}  // namespace

TEST_CASE("file_source resolves a plain path against the parent's directory", "[files][resolve]") {
    const scratch dir("plain");
    dir.write("main.conf", "");
    dir.write("sink.conf", "fps 20hz;\n");
    CHECK(resolve("sink.conf", dir.path("main.conf")) == strings{dir.path("sink.conf")});
    CHECK(resolve(dir.path("main.conf"), "") == strings{dir.path("main.conf")});  // the root, no parent
}

TEST_CASE("file_source resolves '..' and '.' by POSIX rules", "[files][resolve]") {
    const scratch dir("dots");
    dir.write("sink.conf", "");
    dir.write("sub/deep/main.conf", "");
    CHECK(resolve("../.././sink.conf", dir.path("sub/deep/main.conf")) == strings{dir.path("sink.conf")});
}

TEST_CASE("file_source takes an absolute spec as is", "[files][resolve]") {
    const scratch dir("absolute");
    dir.write("sink.conf", "");
    dir.write("other/main.conf", "");
    const std::string absolute = fs::absolute(dir.path("sink.conf")).lexically_normal().generic_string();
    CHECK(resolve(absolute, dir.path("other/main.conf")) == strings{absolute});
}

TEST_CASE("file_source lists a glob's directory and keeps the matching regular files", "[files][resolve]") {
    const scratch dir("glob");
    dir.write("main.conf", "");
    dir.write("sinks/a.conf", "");
    dir.write("sinks/b.conf", "");
    dir.write("sinks/long.conf", "");
    dir.write("sinks/notes.txt", "");
    fs::create_directories(dir.path("sinks/c.conf"));  // a directory: never a match
    const std::string parent = dir.path("main.conf");
    CHECK(resolve("sinks/*.conf", parent) ==
          strings{dir.path("sinks/a.conf"), dir.path("sinks/b.conf"), dir.path("sinks/long.conf")});
    CHECK(resolve("sinks/?.conf", parent) == strings{dir.path("sinks/a.conf"), dir.path("sinks/b.conf")});
    CHECK(resolve("sinks/*", parent).size() == 4);
    CHECK(resolve("sinks/*.ini", parent).empty());
}

TEST_CASE("file_source resolves nothing when nothing is there", "[files][resolve]") {
    const scratch dir("missing");
    dir.write("main.conf", "");
    fs::create_directories(dir.path("folder"));
    const std::string parent = dir.path("main.conf");
    CHECK(resolve("absent.conf", parent).empty());
    CHECK(resolve("folder", parent).empty());  // a directory is not a file
    CHECK(resolve("nowhere/*.conf", parent).empty());
    CHECK(resolve("main.conf/inside.conf", parent).empty());  // through a file
}

TEST_CASE("file_source reads the bytes whole and raises on a missing file", "[files][read]") {
    const scratch dir("read");
    const std::string text = "a 1;\r\nb \"\xc3\xa9\";\n";
    dir.write("main.conf", text);
    const std::shared_ptr<vl::document_source> source = vl::files::file_source();
    CHECK(source->read(dir.path("main.conf")) == text);
    CHECK_THROWS_AS(source->read(dir.path("absent.conf")), std::exception);
}

TEST_CASE("file_writer writes a batch and leaves no temporaries", "[files][write]") {
    const scratch dir("write");
    dir.write("a.conf", "old a\n");
    vl::files::file_writer()->write({vl::file_write(dir.path("a.conf"), "new a\n", "old a\n"),
                                     vl::file_write(dir.path("b.conf"), "new b\n", "")});  // b is created
    CHECK(dir.read("a.conf") == "new a\n");
    CHECK(dir.read("b.conf") == "new b\n");
    CHECK(dir.names("") == strings{"a.conf", "b.conf"});
}

TEST_CASE("file_writer refuses a lost update with exactly the changed paths and writes nothing", "[files][write]") {
    const scratch dir("lost");
    dir.write("a.conf", "a as read\n");
    dir.write("b.conf", "b changed by someone else\n");
    dir.write("c.conf", "c changed too\n");
    std::optional<std::vector<std::string>> lost;
    try {
        vl::files::file_writer()->write({vl::file_write(dir.path("a.conf"), "new a\n", "a as read\n"),
                                         vl::file_write(dir.path("b.conf"), "new b\n", "b as read\n"),
                                         vl::file_write(dir.path("c.conf"), "new c\n", "c as read\n"),
                                         vl::file_write(dir.path("d.conf"), "new d\n", "d as read\n")});
    } catch (const vl::lost_update_error& error) {
        const vl::sequence<std::string> paths = error.paths();
        lost.emplace(paths.begin(), paths.end());
    }
    REQUIRE(lost.has_value());
    CHECK(*lost == strings{dir.path("b.conf"), dir.path("c.conf"), dir.path("d.conf")});  // d: absent reads as empty
    CHECK(dir.read("a.conf") == "a as read\n");
    CHECK(dir.read("b.conf") == "b changed by someone else\n");
    CHECK(dir.names("") == strings{"a.conf", "b.conf", "c.conf"});
}

TEST_CASE("file_writer commits nothing when staging fails", "[files][write]") {
    const scratch dir("staging");
    dir.write("a.conf", "old a\n");
    CHECK_THROWS_AS(vl::files::file_writer()->write({vl::file_write(dir.path("a.conf"), "new a\n", "old a\n"),
                                                     vl::file_write(dir.path("gone/b.conf"), "new b\n", "")}),
                    std::exception);
    CHECK(dir.read("a.conf") == "old a\n");
    CHECK(dir.names("") == strings{"a.conf"});  // the staged temporary of a.conf is removed
}

TEST_CASE("file_writer replaces a symbolic link's target and keeps the file's permissions", "[files][write]") {
    const scratch dir("link");
    dir.write("real/s.conf", "secret 1;\n");
    fs::create_directories(dir.path("w"));
    fs::create_symlink("../real/s.conf", dir.path("w/link.conf"));
    fs::permissions(dir.path("real/s.conf"), fs::perms::owner_read | fs::perms::owner_write, fs::perm_options::replace);
    vl::files::file_writer()->write({vl::file_write(dir.path("w/link.conf"), "secret 2;\n", "secret 1;\n")});
    CHECK(fs::is_symlink(dir.path("w/link.conf")));   // still a link
    CHECK(dir.read("real/s.conf") == "secret 2;\n");  // the edit reached the real file
    CHECK(fs::status(dir.path("real/s.conf")).permissions() == (fs::perms::owner_read | fs::perms::owner_write));
    CHECK(dir.names("real") == strings{"s.conf"});  // no temporary left beside it
    CHECK(dir.names("w") == strings{"link.conf"});
}
