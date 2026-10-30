// The switches every villanelle header reads (design.md 2.2, 2.5; frozen-m1.md section 5).
//   VILLANELLE_HEADER_ONLY  1 (default): every definition is inline in the headers. 0: compiled mode, the program
//                           compiles <villanelle/implementation.hpp> in exactly one file (CMake: VILLANELLE_COMPILED).
//   VILLANELLE_API          what every declaration and definition of a non-template function carries: inline in
//                           header-only mode, nothing in compiled mode.
//   VILLANELLE_EXCEPTIONS   1 when the program is compiled with exceptions (detail/raise.hpp throws, else aborts).
//   VILLANELLE_NAMESPACE_BEGIN / _END  open and close namespace villanelle with its versioned inline namespace, so two
//                           villanelle versions in one program get different symbols (design.md 2.5, D28).
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

#define VILLANELLE_NAMESPACE_BEGIN \
    namespace villanelle {         \
    inline namespace v0 {
#define VILLANELLE_NAMESPACE_END \
    }                            \
    }

#endif  // VILLANELLE_SUPPORT_CONFIG_HPP
