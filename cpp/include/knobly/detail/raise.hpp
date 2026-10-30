// The one throw site (design.md 2.2, D30; frozen-m1.md section 5): with exceptions it throws `error`; without, it
// writes the error's what() to standard error and calls std::abort(), as the standard library does under
// -fno-exceptions. Every knobly throw goes through it; no other file writes `throw`. It is also the one home of
// `try` outside diagnostics::collect (frozen-m2.md 3.3 rule 7): the ports signal failure by throwing, and load and save
// catch a std::exception through catch_exception and look at it through the helpers below.
#ifndef KNOBLY_DETAIL_RAISE_HPP
#define KNOBLY_DETAIL_RAISE_HPP

#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <string>
#include <utility>

#include <knobly/support/config.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace detail {

template <class Error>
[[noreturn]] void raise(const Error& error) {
#if KNOBLY_EXCEPTIONS
    throw error;
#else
    std::fputs(error.what(), stderr);
    std::fputc('\n', stderr);
    std::abort();
#endif
}

/// Raises index_out_of_range for an index at or past size. Declared here for the support templates, which cannot
/// name the error class (errors.hpp includes them); defined with the shared layer (detail/shared/definitions.hpp).
[[noreturn]] KNOBLY_API void raise_index_out_of_range(std::size_t index, std::size_t size);

/// Raises index_out_of_range for ordered_map::at of a key it does not hold (errata T3: the same reason).
[[noreturn]] KNOBLY_API void raise_missing_key();

/// Calls f(); a std::exception it throws is caught and returned instead (null when f returned). Anything else passes
/// through. Without exceptions, a failing f has already ended the program, so this only calls it.
template <class F>
std::exception_ptr catch_exception(F&& f) {
#if KNOBLY_EXCEPTIONS
    try {
        std::forward<F>(f)();
    } catch (const std::exception&) {
        return std::current_exception();
    }
#else
    std::forward<F>(f)();
#endif
    return nullptr;
}

/// The what() of an exception catch_exception caught.
inline std::string message_of(const std::exception_ptr& error) {
#if KNOBLY_EXCEPTIONS
    try {
        std::rethrow_exception(error);
    } catch (const std::exception& caught) {
        return caught.what();
    } catch (...) {
        return "unknown exception";
    }
#else
    static_cast<void>(error);
    return {};
#endif
}

/// Whether the caught exception is an Error (or a class derived from it); when it is, read(it) is called first.
template <class Error, class F>
bool when_caught(const std::exception_ptr& error, F&& read) {
#if KNOBLY_EXCEPTIONS
    try {
        std::rethrow_exception(error);
    } catch (const Error& caught) {
        std::forward<F>(read)(caught);
        return true;
    } catch (...) {
        return false;
    }
#else
    static_cast<void>(error);
    static_cast<void>(read);
    return false;
#endif
}

/// Passes a caught exception on unchanged.
[[noreturn]] inline void rethrow(const std::exception_ptr& error) {
#if KNOBLY_EXCEPTIONS
    std::rethrow_exception(error);
#else
    static_cast<void>(error);
    std::abort();
#endif
}

/// Raises `error` with the caught exception nested in it (std::throw_with_nested), so std::rethrow_if_nested gives the
/// cause back.
template <class Error>
[[noreturn]] void raise_nested(const Error& error, const std::exception_ptr& cause) {
#if KNOBLY_EXCEPTIONS
    try {
        std::rethrow_exception(cause);
    } catch (...) {
        std::throw_with_nested(error);
    }
#else
    static_cast<void>(cause);
    raise(error);
#endif
}

}  // namespace detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_RAISE_HPP
