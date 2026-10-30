// The rendered definitions' entry point: <knobly/rendered.hpp> includes it at its end in header-only mode, and
// <knobly/implementation.hpp> in compiled mode. Every definition here carries KNOBLY_API (or is inline or a
// template). The layer: nodes.hpp (what a view points at), tree.hpp (the render, directives, blocks, addresses),
// render.hpp (render), diff.hpp (diff and its changes); a port of ts/src/rendered/{render,tree,diff}.ts.
#ifndef KNOBLY_DETAIL_RENDERED_DEFINITIONS_HPP
#define KNOBLY_DETAIL_RENDERED_DEFINITIONS_HPP

#include <knobly/detail/rendered/diff.hpp>
#include <knobly/detail/rendered/nodes.hpp>
#include <knobly/detail/rendered/render.hpp>
#include <knobly/detail/rendered/tree.hpp>
#include <knobly/rendered.hpp>

#endif  // KNOBLY_DETAIL_RENDERED_DEFINITIONS_HPP
