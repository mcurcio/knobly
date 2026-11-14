#!/usr/bin/env bash
# Build the C++ release assets for one version into a directory (default dist/release/, ignored by git):
#   knobly-cpp-<version>.tar.gz   the C++ source archive: cpp/CMakeLists.txt, cpp/include/ with the generated
#                                     headers, cpp/README.md and LICENSE, under knobly-cpp-<version>/. A program
#                                     takes it with FetchContent or add_subdirectory (CMake 3.24+, a C++20 compiler):
#                                     no Python, no network beyond the download, nothing installed.
#   knobly.hpp                    the single header (tools/amalgamate.py), from the archive's headers
# The version is stamped into the archive's copy of include/knobly/support/config.hpp (the C++ version's one
# home), never into the repository. Run by .github/release-build.sh (semantic-release's prepare step, and the
# dry-run release job) and by the C++ package job in .github/workflows/ci.yml (cpp/tests/consumer/check.sh).
# Needs: python3 (3.9+), uv (tools/gen.sh cpp, for the pinned clang-format) and git.
set -euo pipefail
cd "$(dirname "$0")/.."

version="${1:?usage: .github/release-cpp.sh <version> [out-dir]}"
out="${2:-dist/release}"
[[ "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)([-+].*)?$ ]] || { echo "release-cpp.sh: not a version: $version" >&2; exit 1; }
major=${BASH_REMATCH[1]} minor=${BASH_REMATCH[2]} patch=${BASH_REMATCH[3]}

bash tools/gen.sh cpp

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
name="knobly-cpp-$version"
dir="$stage/$name"
mkdir -p "$dir"
cp cpp/CMakeLists.txt cpp/README.md LICENSE "$dir/"
# The headers without the generators' temporary folders (dot names).
(cd cpp && find include -name '.*' -prune -o -type f -name '*.hpp' -print) | while read -r file; do
  mkdir -p "$dir/$(dirname "$file")"
  cp "cpp/$file" "$dir/$file"
done

config="$dir/include/knobly/support/config.hpp"
python3 - "$config" "$major" "$minor" "$patch" <<'EOF'
import re, sys
path, *parts = sys.argv[1:]
text = open(path, encoding="utf-8").read()
for name, value in zip(("MAJOR", "MINOR", "PATCH"), parts):
    text, count = re.subn(rf"^#define KNOBLY_VERSION_{name} \d+$", f"#define KNOBLY_VERSION_{name} {value}",
                          text, flags=re.M)
    if count != 1:
        sys.exit(f"release-cpp.sh: {path}: expected one KNOBLY_VERSION_{name}, found {count}")
open(path, "w", encoding="utf-8").write(text)
EOF

mkdir -p "$out"
# A reproducible archive, the same bytes from the same commit on any machine: entries sorted, every mtime
# $SOURCE_DATE_EPOCH (default: the commit's time), owner 0 and no names, modes 644 and 755, no gzip name or time.
# One top-level entry and no extended attributes or macOS metadata files (._*): a second top-level entry stops
# FetchContent from stripping the knobly-cpp-<version>/ folder.
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct)}" python3 - "$stage" "$name" "$out/$name.tar.gz" <<'EOF2'
import gzip, os, sys, tarfile
stage, name, dest = sys.argv[1:]
mtime = int(os.environ["SOURCE_DATE_EPOCH"])
paths = [name]
for root, dirs, files in os.walk(os.path.join(stage, name)):
    paths += [os.path.relpath(os.path.join(root, f), stage) for f in dirs + files]
with open(dest, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
    with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(paths):
            info = tar.gettarinfo(os.path.join(stage, path), arcname=path)
            info.mtime, info.uid, info.gid, info.uname, info.gname = mtime, 0, 0, "", ""
            info.mode = 0o755 if info.isdir() else 0o644
            if info.isdir():
                tar.addfile(info)
            else:
                with open(os.path.join(stage, path), "rb") as f:
                    tar.addfile(info, f)
EOF2
python3 tools/amalgamate.py --include "$dir/include" --output "$out/knobly.hpp"
ls -l "$out/$name.tar.gz" "$out/knobly.hpp"
