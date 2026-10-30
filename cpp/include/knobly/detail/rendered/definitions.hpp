// The rendered definitions' entry point: <villanelle/rendered.hpp> includes it at its end in header-only mode, and
// <villanelle/implementation.hpp> in compiled mode. Every definition here carries VILLANELLE_API (or is inline or a
// template). The layer: nodes.hpp (what a view points at), tree.hpp (the render, directives, blocks, addresses),
// render.hpp (render), diff.hpp (diff and its changes); a port of ts/src/rendered/{render,tree,diff}.ts.
#ifndef VILLANELLE_DETAIL_RENDERED_DEFINITIONS_HPP
#define VILLANELLE_DETAIL_RENDERED_DEFINITIONS_HPP

#include <villanelle/detail/rendered/diff.hpp>
#include <villanelle/detail/rendered/nodes.hpp>
#include <villanelle/detail/rendered/render.hpp>
#include <villanelle/detail/rendered/tree.hpp>
#include <villanelle/rendered.hpp>

#endif  // VILLANELLE_DETAIL_RENDERED_DEFINITIONS_HPP
