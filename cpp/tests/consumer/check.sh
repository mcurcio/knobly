#!/usr/bin/env bash
# Build and run consumer.cpp by every route a program takes knobly (cpp/README.md, "Using it"), from the release
# assets .github/release-cpp.sh writes: FetchContent of the source archive, header-only and compiled; add_subdirectory
# of the extracted archive; the single header alone. Nothing is installed anywhere, and python, python3, uv and curl
# are stubs that fail if called, so no route needs them. Each program exits 0 only on the expected output, and its
# symbols must carry the stamped inline namespace (knobly::v<major>_<minor>_<patch>). CI's C++ package job runs
# it; locally:
#
#   bash .github/release-cpp.sh 1.2.3 <work>/assets && bash cpp/tests/consumer/check.sh 1.2.3 <work>/assets <work>
#
# Needs CMake 3.24+, a C++20 compiler ($CXX, else c++), nm and tar.
set -euo pipefail
cd "$(dirname "$0")"
here=$(pwd)

version="${1:?usage: check.sh <version> <assets-dir> <work-dir>}"
assets=$(cd "${2:?usage: check.sh <version> <assets-dir> <work-dir>}" && pwd)
work="${3:?usage: check.sh <version> <assets-dir> <work-dir>}"
mkdir -p "$work"
work=$(cd "$work" && pwd)
archive="$assets/knobly-cpp-$version.tar.gz"
core="${version%%[-+]*}"
namespace="knobly::v${core//./_}::"

rm -rf "$work/stubs" "$work/archive" "$work"/consumer-*
mkdir -p "$work/stubs" "$work/archive"
for tool in python python3 uv curl; do
  printf '#!/bin/sh\necho "%s was called: using knobly must not need it" >&2\nexit 1\n' "$tool" \
    > "$work/stubs/$tool"
  chmod +x "$work/stubs/$tool"
done
export PATH="$work/stubs:$PATH"

# Runs a built consumer and checks its symbols carry the stamped inline namespace.
run() {
  "$1"
  local count
  count=$(nm -C "$1" | grep -c "$namespace") || { echo "check.sh: $1: no symbol in $namespace" >&2; exit 1; }
  echo "$1: expected output, $count symbols in $namespace"
}

# FetchContent of the archive (a file:// URL with its hash) into the consumer's build folder, in both modes.
sha256=$(cmake -E sha256sum "$archive" | cut -d' ' -f1)
for compiled in OFF ON; do
  build="$work/consumer-fetchcontent-$compiled"
  cmake -S "$here" -B "$build" -DKNOBLY_RELEASE_URL="file://$archive" -DKNOBLY_RELEASE_SHA256="$sha256" \
    -DKNOBLY_COMPILED="$compiled"
  grep -qx 'KNOBLY_REGENERATE:BOOL=OFF' "$build/CMakeCache.txt"
  grep -qx 'KNOBLY_BUILD_TESTS:BOOL=OFF' "$build/CMakeCache.txt"
  cmake --build "$build"
  run "$build/consumer"
done

# add_subdirectory of the extracted archive.
tar -C "$work/archive" -xzf "$archive"
build="$work/consumer-subdirectory"
cmake -S "$here/../consumer-subdirectory" -B "$build" -DKNOBLY_SOURCE="$work/archive/knobly-cpp-$version"
grep -qx 'KNOBLY_REGENERATE:BOOL=OFF' "$build/CMakeCache.txt"
cmake --build "$build"
run "$build/consumer"

# The single header alone: the include path holds knobly.hpp and nothing else.
mkdir -p "$work/consumer-single"
cp "$assets/knobly.hpp" "$work/consumer-single/"
"${CXX:-c++}" -std=c++20 -Wall -Wextra -Werror -DKNOBLY_SINGLE_HEADER -I"$work/consumer-single" \
  "$here/consumer.cpp" -o "$work/consumer-single/consumer"
run "$work/consumer-single/consumer"
