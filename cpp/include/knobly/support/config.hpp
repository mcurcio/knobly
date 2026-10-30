// The switches every knobly header reads (design.md 2.2, 2.5; frozen-m1.md section 5).
//   KNOBLY_HEADER_ONLY  1 (default): every definition is inline in the headers. 0: compiled mode, the program
//                           compiles <knobly/implementation.hpp> in exactly one file (CMake: KNOBLY_COMPILED).
//   KNOBLY_API          what every declaration and definition of a non-template function carries: inline in
//                           header-only mode, nothing in compiled mode.
//   KNOBLY_EXCEPTIONS   1 when the program is compiled with exceptions (detail/raise.hpp throws, else aborts).
//   KNOBLY_VERSION_MAJOR / _MINOR / _PATCH  the release's version: 0.0.0 in the repository, stamped into the
//                           release source archive and the single header by .github/release-cpp.sh. The one home
//                           of the C++ version: cpp/CMakeLists.txt reads it from here.
//   KNOBLY_NAMESPACE_BEGIN / _END  open and close namespace knobly with its versioned inline namespace,
//                           v<major>_<minor>_<patch>, so two knobly versions in one program get different symbols
//                           (design.md 2.5, D28).
#ifndef KNOBLY_SUPPORT_CONFIG_HPP
#define KNOBLY_SUPPORT_CONFIG_HPP

#ifndef KNOBLY_HEADER_ONLY
#define KNOBLY_HEADER_ONLY 1
#endif

#if KNOBLY_HEADER_ONLY
#define KNOBLY_API inline
#else
#define KNOBLY_API
#endif

#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || (defined(_HAS_EXCEPTIONS) && _HAS_EXCEPTIONS)
#define KNOBLY_EXCEPTIONS 1
#else
#define KNOBLY_EXCEPTIONS 0
#endif

#define KNOBLY_VERSION_MAJOR 0
#define KNOBLY_VERSION_MINOR 0
#define KNOBLY_VERSION_PATCH 0

#define KNOBLY_DETAIL_ABI_NAME(major, minor, patch) v##major##_##minor##_##patch
#define KNOBLY_DETAIL_ABI(major, minor, patch) KNOBLY_DETAIL_ABI_NAME(major, minor, patch)
#define KNOBLY_NAMESPACE_BEGIN \
    namespace knobly {         \
    inline namespace KNOBLY_DETAIL_ABI(KNOBLY_VERSION_MAJOR, KNOBLY_VERSION_MINOR, KNOBLY_VERSION_PATCH) {
#define KNOBLY_NAMESPACE_END \
    }                        \
    }

#endif  // KNOBLY_SUPPORT_CONFIG_HPP
