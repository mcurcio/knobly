// The io definitions' entry point: <knobly/knobly.hpp> includes it at its end in header-only mode, and
// <knobly/implementation.hpp> in compiled mode (frozen-m1.md section 5). Every definition here carries
// KNOBLY_API (or is a template).
#ifndef KNOBLY_DETAIL_IO_DEFINITIONS_HPP
#define KNOBLY_DETAIL_IO_DEFINITIONS_HPP

#include <knobly/detail/io/lost_updates.hpp>
#include <knobly/detail/io/memory.hpp>
#include <knobly/detail/io/paths.hpp>

#endif  // KNOBLY_DETAIL_IO_DEFINITIONS_HPP
