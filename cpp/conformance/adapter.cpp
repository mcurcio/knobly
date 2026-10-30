// The C++ binding's conformance adapter (spec/conformance.md): the shared driver runs the corpora through it over
// standard input and output. Milestone 1 claims level 0 with "unit": "byte" (frozen-m1.md section 6).
// SKELETON: compiles against the public headers and answers nothing yet; Slice T writes the request loop.
#include <villanelle/syntax.hpp>
#include <villanelle/villanelle.hpp>

#include <cstdio>
#include <cstdlib>

#include "json.hpp"
#include "shapes.hpp"

int main() {
    std::fputs("villanelle cpp adapter: not built yet (milestone 1, Slice T)\n", stderr);
    return EXIT_FAILURE;
}
