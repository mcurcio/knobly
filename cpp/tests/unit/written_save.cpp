// save (spec 4.2, 6.8; design program 4.2): one batch of the changed documents, their saved text moving only when the
// writer returns; a lost update passes through unchanged; any other failure of the writer is a save_error with the
// writer's exception nested (std::rethrow_if_nested gives it back).
#include <villanelle/extensions.hpp>
#include <villanelle/written.hpp>

#include <exception>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = villanelle;
namespace vw = villanelle::written;

namespace {

/// Records every batch; fails with `failure` when one is set.
class recorder final : public vl::document_writer {
public:
    void write(vl::sequence<vl::file_write> files) const override {
        batches->push_back(files);
        if (!failure->empty()) {
            throw std::runtime_error(*failure);
        }
    }
    std::shared_ptr<std::vector<vl::sequence<vl::file_write>>> batches =
        std::make_shared<std::vector<vl::sequence<vl::file_write>>>();
    std::shared_ptr<std::string> failure = std::make_shared<std::string>();
};

const auto texts = [] {
    return fixture::files({{"main.conf", "a 1;\n"}, {"other.conf", "b 2;\n"}, {"third.conf", "c 3;\n"}});
};

}  // namespace

TEST_CASE("save hands the changed documents to the writer in one batch", "[save]") {
    const auto files = fixture::files({{"main.conf", "a 1;\n@include \"other.conf\";\n@include \"third.conf\";\n"},
                                       {"other.conf", "b 2;\n"},
                                       {"third.conf", "c 3;\n"}});
    const vw::document_graph graph =
        vw::processor({vl::memory_source(files), {vl::extensions::include()}}).load("main.conf");
    REQUIRE(graph.documents().size() == 3);
    auto writer = std::make_shared<recorder>();
    CHECK(graph.save(writer).empty());
    CHECK(writer->batches->empty());  // nothing changed: the writer is not called
    graph.root().block().at(0).as<vw::written_directive>()->set(vl::text("10"));
    graph.documents().at("third.conf").block().at(0).as<vw::written_directive>()->set(vl::text("30"));
    const vl::sequence<std::string> saved = graph.save(writer);
    CHECK(saved == vl::sequence<std::string>{"main.conf", "third.conf"});
    REQUIRE(writer->batches->size() == 1);
    const vl::sequence<vl::file_write> batch = writer->batches->at(0);
    REQUIRE(batch.size() == 2);
    CHECK(batch.at(0).resolved_path() == "main.conf");
    CHECK(batch.at(0).text() == "a 10;\n@include \"other.conf\";\n@include \"third.conf\";\n");
    CHECK(batch.at(0).saved_text() == "a 1;\n@include \"other.conf\";\n@include \"third.conf\";\n");
    CHECK(batch.at(1).resolved_path() == "third.conf");
    CHECK(batch.at(1).text() == "c 30;\n");
    CHECK(graph.documents().at("third.conf").saved_text() == "c 30;\n");
    CHECK(graph.documents().at("other.conf").saved_text() == "b 2;\n");
    CHECK(graph.save(writer).empty());  // saved: nothing changed since
}

TEST_CASE("a failing writer: save_error with its exception nested, saved text unmoved", "[save]") {
    const vw::document_graph graph = fixture::load(texts());
    graph.root().block().at(0).as<vw::written_directive>()->set(vl::text("10"));
    auto writer = std::make_shared<recorder>();
    *writer->failure = "disk full";
    bool nested = false;
    try {
        graph.save(writer);
        FAIL("save did not raise");
    } catch (const vl::lost_update_error&) {
        FAIL("a writer's failure is not a lost update");
    } catch (const vl::save_error& error) {
        CHECK(error.paths() == vl::sequence<std::string>{"main.conf"});
        CHECK(std::string(error.what()).find("disk full") != std::string::npos);
        try {
            std::rethrow_if_nested(error);
        } catch (const std::runtime_error& cause) {
            nested = std::string(cause.what()) == "disk full";
        }
    }
    CHECK(nested);
    CHECK(graph.root().saved_text() == "a 1;\n");
    CHECK(graph.root().text() == "a 10;\n");
    *writer->failure = "";
    CHECK(graph.save(writer) == vl::sequence<std::string>{"main.conf"});
    CHECK(graph.root().saved_text() == "a 10;\n");
}

TEST_CASE("a lost update passes through save unchanged, and nothing is written", "[save]") {
    const auto files = texts();
    const vw::document_graph graph = fixture::load(files);
    graph.root().block().at(0).as<vw::written_directive>()->set(vl::text("10"));
    files->insert_or_assign("main.conf", "changed elsewhere;\n");
    try {
        graph.save(vl::memory_writer(files));
        FAIL("save did not raise");
    } catch (const vl::lost_update_error& error) {
        CHECK(error.paths() == vl::sequence<std::string>{"main.conf"});
        bool has_nested = true;
        try {
            std::rethrow_if_nested(error);
            has_nested = false;
        } catch (...) {
        }
        CHECK_FALSE(has_nested);  // passed through as the writer raised it
    }
    CHECK(files->at("main.conf") == "changed elsewhere;\n");
    CHECK(graph.root().saved_text() == "a 1;\n");
    // The medium agrees again: the save goes through, and the next load sees it.
    files->insert_or_assign("main.conf", "a 1;\n");
    CHECK(graph.save(vl::memory_writer(files)) == vl::sequence<std::string>{"main.conf"});
    CHECK(fixture::load(files).root().text() == "a 10;\n");
}

TEST_CASE("save with no writer is an argument type error", "[save]") {
    const vw::document_graph graph = fixture::load(texts());
    CHECK_THROWS_AS(graph.save(nullptr), vl::argument_type_error);
}
