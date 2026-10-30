#!/usr/bin/env bash
# Build the C++ release assets for one version into a directory (default dist/release/, ignored by git):
#   villanelle-cpp-<version>.tar.gz   the C++ source archive: cpp/CMakeLists.txt, cpp/include/ with the generated
#                                     headers, cpp/README.md and LICENSE, under villanelle-cpp-<version>/. CMake 3.24+
#                                     and a C++20 compiler build and install it with no Python and no network.
#   villanelle.hpp                    the single header (tools/amalgamate.py), from the archive's headers
# The version is stamped into the archive's copy of include/villanelle/support/config.hpp (the C++ version's one
# home), never into the repository. Run by .github/release-build.sh (semantic-release's prepare step, and the
# dry-run release job) and by the C++ package job in .github/workflows/ci.yml.
# Needs: python3 (3.9+) and uv (tools/gen.sh cpp, for the pinned clang-format), tar.
set -euo pipefail
cd "$(dirname "$0")/.."

version="${1:?usage: .github/release-cpp.sh <version> [out-dir]}"
out="${2:-dist/release}"
[[ "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)([-+].*)?$ ]] || { echo "release-cpp.sh: not a version: $version" >&2; exit 1; }
major=${BASH_REMATCH[1]} minor=${BASH_REMATCH[2]} patch=${BASH_REMATCH[3]}

bash tools/gen.sh cpp

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
name="villanelle-cpp-$version"
dir="$stage/$name"
mkdir -p "$dir"
cp cpp/CMakeLists.txt cpp/README.md LICENSE "$dir/"
# The headers without the generators' temporary folders (dot names).
(cd cpp && find include -name '.*' -prune -o -type f -name '*.hpp' -print) | while read -r file; do
  mkdir -p "$dir/$(dirname "$file")"
  cp "cpp/$file" "$dir/$file"
done

config="$dir/include/villanelle/support/config.hpp"
python3 - "$config" "$major" "$minor" "$patch" <<'EOF'
import re, sys
path, *parts = sys.argv[1:]
text = open(path, encoding="utf-8").read()
for name, value in zip(("MAJOR", "MINOR", "PATCH"), parts):
    text, count = re.subn(rf"^#define VILLANELLE_VERSION_{name} \d+$", f"#define VILLANELLE_VERSION_{name} {value}",
                          text, flags=re.M)
    if count != 1:
        sys.exit(f"release-cpp.sh: {path}: expected one VILLANELLE_VERSION_{name}, found {count}")
open(path, "w", encoding="utf-8").write(text)
EOF

mkdir -p "$out"
tar -C "$stage" -czf "$out/$name.tar.gz" "$name"
python3 tools/amalgamate.py --include "$dir/include" --output "$out/villanelle.hpp"
ls -l "$out/$name.tar.gz" "$out/villanelle.hpp"
