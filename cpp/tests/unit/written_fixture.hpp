// What the written-layer unit programs share: a graph loaded from texts in memory, and its statements by name.
#ifndef KNOBLY_TESTS_UNIT_WRITTEN_FIXTURE_HPP
#define KNOBLY_TESTS_UNIT_WRITTEN_FIXTURE_HPP

#include <knobly/knobly.hpp>
#include <knobly/written.hpp>

#include <initializer_list>
#include <memory>
#include <string>
#include <utility>

namespace fixture {

namespace vl = knobly;
namespace vw = knobly::written;

/// The texts a memory source serves, shared so a memory writer's change is seen.
inline std::shared_ptr<vl::ordered_map<std::string, std::string>> files(
    std::initializer_list<std::pair<std::string, std::string>> texts) {
    auto out = std::make_shared<vl::ordered_map<std::string, std::string>>();
    for (const auto& [path, text] : texts) {
        out->insert_or_assign(path, text);
    }
    return out;
}

/// The graph of `root` over those texts.
inline vw::document_graph load(const std::shared_ptr<vl::ordered_map<std::string, std::string>>& texts,
                               const std::string& root = "main.conf", vw::load_options options = {}) {
    return vw::processor({vl::memory_source(texts), {}}).load(root, std::move(options));
}

/// The graph of one file, main.conf.
inline vw::document_graph load(const std::string& text) { return load(files({{"main.conf", text}})); }

/// The top-level statement at `index` of the root document.
inline vw::statement top(const vw::document_graph& graph, std::size_t index) { return graph.root().block().at(index); }

}  // namespace fixture

#endif  // KNOBLY_TESTS_UNIT_WRITTEN_FIXTURE_HPP
