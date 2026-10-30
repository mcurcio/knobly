// The switches every villanelle header reads (design.md 2.2, 2.5; frozen-m1.md section 5).
//   VILLANELLE_HEADER_ONLY  1 (default): every definition is inline in the headers. 0: compiled mode, the program
//                           compiles <villanelle/implementation.hpp> in exactly one file (CMake: VILLANELLE_COMPILED).
//   VILLANELLE_API          what every declaration and definition of a non-template function carries: inline in
//                           header-only mode, nothing in compiled mode.
//   VILLANELLE_EXCEPTIONS   1 when the program is compiled with exceptions (detail/raise.hpp throws, else aborts).
//   VILLANELLE_VERSION_MAJOR / _MINOR / _PATCH  the release's version: 0.0.0 in the repository, stamped into the
//                           release source archive and the single header by .github/release-cpp.sh. The one home
//                           of the C++ version: cpp/CMakeLists.txt reads it from here.
//   VILLANELLE_NAMESPACE_BEGIN / _END  open and close namespace villanelle with its versioned inline namespace,
//                           v<major>_<minor>_<patch>, so two villanelle versions in one program get different symbols
//                           (design.md 2.5, D28).
#ifndef VILLANELLE_SUPPORT_CONFIG_HPP
#define VILLANELLE_SUPPORT_CONFIG_HPP

#ifndef VILLANELLE_HEADER_ONLY
#define VILLANELLE_HEADER_ONLY 1
#endif

#if VILLANELLE_HEADER_ONLY
#define VILLANELLE_API inline
#else
#define VILLANELLE_API
#endif

#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || (defined(_HAS_EXCEPTIONS) && _HAS_EXCEPTIONS)
#define VILLANELLE_EXCEPTIONS 1
#else
#define VILLANELLE_EXCEPTIONS 0
#endif

#define VILLANELLE_VERSION_MAJOR 0
#define VILLANELLE_VERSION_MINOR 0
#define VILLANELLE_VERSION_PATCH 0

#define VILLANELLE_DETAIL_ABI_NAME(major, minor, patch) v##major##_##minor##_##patch
#define VILLANELLE_DETAIL_ABI(major, minor, patch) VILLANELLE_DETAIL_ABI_NAME(major, minor, patch)
#define VILLANELLE_NAMESPACE_BEGIN                                                             \
    namespace villanelle {                                                                     \
    inline namespace VILLANELLE_DETAIL_ABI(VILLANELLE_VERSION_MAJOR, VILLANELLE_VERSION_MINOR, \
                                           VILLANELLE_VERSION_PATCH) {
#define VILLANELLE_NAMESPACE_END \
    }                            \
    }

#endif  // VILLANELLE_SUPPORT_CONFIG_HPP
