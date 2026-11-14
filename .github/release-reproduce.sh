#!/usr/bin/env bash
# Prove the release assets are reproducible from the commit: build them twice, in this checkout and in a fresh
# worktree of the same commit at another path (another time, other build folders), and fail unless the two
# SHA256SUMS are identical. CI's release-build job runs it on every push and pull request; locally:
#
#   bash .github/release-reproduce.sh 1.2.3
#
# Needs what .github/release-build.sh needs, and network for the second checkout's pnpm install.
set -euo pipefail
cd "$(dirname "$0")/.."

version="${1:?usage: .github/release-reproduce.sh <version>}"
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "release-reproduce.sh: commit or stash your changes first" >&2; exit 1; }

again=$(mktemp -d)
trap 'git worktree remove --force "$again" > /dev/null 2>&1 || rm -rf "$again"' EXIT
git worktree add --detach "$again" HEAD > /dev/null

bash .github/release-build.sh "$version" > /dev/null
(cd "$again" && corepack pnpm -C ts install --frozen-lockfile > /dev/null && bash .github/release-build.sh "$version" > /dev/null)

if diff -u dist/release/SHA256SUMS "$again/dist/release/SHA256SUMS"; then
  echo "release-reproduce.sh: two builds of $(git rev-parse --short HEAD), byte for byte the same:"
  cat dist/release/SHA256SUMS
else
  echo "release-reproduce.sh: the two builds differ (above)" >&2
  exit 1
fi
