// Sample "custom_source" (examples/samples.json): a document source of the program's own, here one that wraps the
// memory source and records every file it reads. ctest examples_custom_source compares what it prints with
// examples/expected/custom_source.txt.
// --8<-- [start:main]
#include <knobly/extensions.hpp>
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

#include <iostream>
#include <memory>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

// --8<-- [start:source]
class recording_source : public vl::document_source {
public:
    explicit recording_source(std::shared_ptr<vl::document_source> inner) : inner_(std::move(inner)) {}

    vl::sequence<std::string> resolve(std::string_view spec, const vl::load_context& context) const override {
        return inner_->resolve(spec, context);
    }
    std::string read(std::string_view resolved_path) const override {
        reads_.emplace_back(resolved_path);
        return inner_->read(resolved_path);
    }
    const std::vector<std::string>& reads() const { return reads_; }

private:
    std::shared_ptr<vl::document_source> inner_;
    mutable std::vector<std::string> reads_;
};
// --8<-- [end:source]

int main() {
    const auto files = std::make_shared<vl::ordered_map<std::string, std::string>>();
    files->insert_or_assign("main.conf",
                            "@include \"sink.conf\" { @set $name a; }\n"
                            "@include \"sink.conf\" { @set $name b; }\n");
    files->insert_or_assign("sink.conf", "sink $name;\n");
    const auto source = std::make_shared<recording_source>(vl::memory_source(files));
    const vw::processor config({.source = source, .extensions = {vl::extensions::include()}});
    const vr::rendered tree = vr::render(config.load("main.conf"));

    std::string sinks;
    for (const vr::directive& sink : tree.block().directives("sink")) {
        sinks += (sinks.empty() ? "" : ", ") + sink.values().at(0).text();
    }
    std::string reads;
    for (const std::string& path : source->reads()) {
        reads += (reads.empty() ? "" : ", ") + path;
    }
    std::cout << "sinks " << sinks << '\n';
    std::cout << "reads " << reads << '\n';  // each file once, though sink.conf is included twice
}
// --8<-- [end:main]
