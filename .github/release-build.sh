#!/usr/bin/env bash
# Build the release assets for one version into dist/release/ (ignored by git):
#   knobly-<version>.tgz                 npm pack of ts/
#   knobly-<version>-py3-none-any.whl    uv build of py/ (wheel)
#   knobly-<version>.tar.gz              uv build of py/ (sdist)
#   knobly-cpp-<version>.tar.gz          the C++ source archive, generated headers included (.github/release-cpp.sh)
#   knobly.hpp                           the C++ single header (.github/release-cpp.sh)
# The version is stamped into ts/package.json and py/pyproject.toml for the build only; both files get their
# committed bytes back on exit, so the version is never committed. Run by semantic-release's prepare step
# (.releaserc.json), in dry-run by the release job in .github/workflows/ci.yml, and on every push and pull request by
# its release-build job.
# Needs: Node 24 with corepack, ts/ dependencies installed, Java 11+ (tools/gen.sh), uv, python3.
set -euo pipefail
cd "$(dirname "$0")/.."

version="${1:?usage: .github/release-build.sh <version>}"
out=dist/release

saved=$(mktemp -d)
cp ts/package.json py/pyproject.toml "$saved/"
restore() { cp "$saved/package.json" ts/package.json; cp "$saved/pyproject.toml" py/pyproject.toml; rm -rf "$saved"; }
trap restore EXIT

rm -rf "$out"
mkdir -p "$out"

# Generate before stamping: generated code does not depend on the version, and the py generator runs ruff through
# `uv run --locked`, which refuses a pyproject.toml whose version no longer matches py/uv.lock.
bash tools/gen.sh py

npm pkg set --prefix ts version="$version"
corepack pnpm -C ts build
npm pack ./ts --pack-destination "$out"

uv version --project py --frozen "$version"
uv build --out-dir "$out" py

bash .github/release-cpp.sh "$version" "$out"

ls -l "$out"
