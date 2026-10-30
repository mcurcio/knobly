// memory_source and memory_writer (spec 4.3): resolve through the shared POSIX join (relative, '..', absolute), globs
// in the last segment, a missing key, reading the map at each call, and the writer's lost-update check.
#include <villanelle/villanelle.hpp>

#include <algorithm>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include <catch2/catch_test_macros.hpp>

namespace vl = villanelle;

namespace {

std::shared_ptr<vl::ordered_map<std::string, std::string>> texts() {
    auto files = std::make_shared<vl::ordered_map<std::string, std::string>>();
    for (const char* path :
         {"main.conf", "conf/a.conf", "conf/b.conf", "conf/ab.txt", "conf/sub/c.conf", "/abs/x.conf"}) {
        files->insert_or_assign(path, std::string("text of ") + path);
    }
    return files;
}

std::vector<std::string> sorted(const vl::sequence<std::string>& paths) {
    std::vector<std::string> out(paths.begin(), paths.end());
    std::sort(out.begin(), out.end());
    return out;
}

}  // namespace

TEST_CASE("resolve joins a spec to its parent's directory by POSIX rules", "[memory]") {
    const auto source = vl::memory_source(texts());
    CHECK(source->resolve("main.conf", vl::load_context("")) == vl::sequence<std::string>{"main.conf"});
    CHECK(source->resolve("a.conf", vl::load_context("conf/b.conf")) == vl::sequence<std::string>{"conf/a.conf"});
    CHECK(source->resolve("../main.conf", vl::load_context("conf/a.conf")) == vl::sequence<std::string>{"main.conf"});
    CHECK(source->resolve("./sub/../a.conf", vl::load_context("conf/b.conf")) ==
          vl::sequence<std::string>{"conf/a.conf"});
    CHECK(source->resolve("/abs/x.conf", vl::load_context("conf/b.conf")) == vl::sequence<std::string>{"/abs/x.conf"});
    CHECK(source->resolve("missing.conf", vl::load_context("")).empty());
}

TEST_CASE("a glob in the last segment matches the keys of that directory", "[memory]") {
    const auto source = vl::memory_source(texts());
    CHECK(sorted(source->resolve("conf/*.conf", vl::load_context(""))) ==
          std::vector<std::string>{"conf/a.conf", "conf/b.conf"});  // not conf/sub/c.conf
    CHECK(sorted(source->resolve("?.conf", vl::load_context("conf/x"))) ==
          std::vector<std::string>{"conf/a.conf", "conf/b.conf"});
    CHECK(sorted(source->resolve("conf/a*", vl::load_context(""))) ==
          std::vector<std::string>{"conf/a.conf", "conf/ab.txt"});
    CHECK(source->resolve("conf/*.none", vl::load_context("")).empty());
}

TEST_CASE("read gives a key's text, fails for a missing one, and sees later changes", "[memory]") {
    const auto files = texts();
    const auto source = vl::memory_source(files);
    CHECK(source->read("conf/a.conf") == "text of conf/a.conf");
    CHECK_THROWS_AS(source->read("nope.conf"), std::runtime_error);
    files->insert_or_assign("nope.conf", "now here");
    CHECK(source->read("nope.conf") == "now here");
    CHECK(source->resolve("nope.conf", vl::load_context("")) == vl::sequence<std::string>{"nope.conf"});
    CHECK_THROWS_AS(vl::memory_source(nullptr), vl::argument_type_error);
    CHECK_THROWS_AS(vl::memory_writer(nullptr), vl::argument_type_error);
}

TEST_CASE("the memory writer writes a batch whole, or nothing on a lost update", "[memory]") {
    const auto files = texts();
    const auto writer = vl::memory_writer(files);
    writer->write(
        {vl::file_write("main.conf", "new main", "text of main.conf"), vl::file_write("fresh.conf", "fresh", "")});
    CHECK(files->at("main.conf") == "new main");
    CHECK(files->at("fresh.conf") == "fresh");  // absent reads as empty
    try {
        writer->write({vl::file_write("main.conf", "newer", "new main"), vl::file_write("conf/a.conf", "x", "stale"),
                       vl::file_write("conf/b.conf", "y", "stale too")});
        FAIL("no lost update raised");
    } catch (const vl::lost_update_error& error) {
        CHECK(error.paths() == vl::sequence<std::string>{"conf/a.conf", "conf/b.conf"});
    }
    CHECK(files->at("main.conf") == "new main");  // nothing written
    CHECK_THROWS_AS(vl::check_lost_updates({vl::file_write("a", "b", "c")}, {}), vl::misuse_error);
}
