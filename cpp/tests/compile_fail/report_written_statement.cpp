// What C++ refuses at compile time (frozen-m3.md 4; spec 7.7): report() takes something locatable (a rendered
// directive, an expanded value, the render), and a written statement is not, so reporting on one does not compile.
// The nearest valid line builds the located diagnostic from the statement's place. Building this file must fail;
// with VILLANELLE_CONTROL it must build.
#include <villanelle/villanelle.hpp>
#include <villanelle/written.hpp>

namespace vl = villanelle;
namespace vw = villanelle::written;

void refused(const vl::diagnostics& problems, const vw::statement& field) {
#ifndef VILLANELLE_CONTROL
    problems.report(field, "'timeout' is deprecated", "svc/deprecated");
#else
    problems.add(vl::located_diagnostic("svc/deprecated", "'timeout' is deprecated", field.place(), {}));
#endif
}
