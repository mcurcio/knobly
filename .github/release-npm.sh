#!/usr/bin/env bash
# Publish the release's npm tarball to GitHub Packages as @mcurcio/knobly (owner, 2026-11-14: keep the package
# `knobly` and publish the same build there under the scope GitHub's npm registry requires).
#   bash .github/release-npm.sh <version> [--dry-run]
# The registry copy is dist/release/knobly-<version>.tgz with only package.json's name changed (and a publishConfig
# naming the registry): the same files, byte for byte. A consumer aliases it back, so its imports stay "knobly/...":
#   "knobly": "npm:@mcurcio/knobly@<version>"   with   @mcurcio:registry=https://npm.pkg.github.com   in .npmrc
# Run by semantic-release's publish step (.releaserc.json) after .github/release-build.sh; in dry-run by the release
# job, with --dry-run (npm publish --dry-run: prints what it would publish, needs no token).
# Needs: Node 24 (npm), tar; NODE_AUTH_TOKEN with write:packages (in CI, the job's GITHUB_TOKEN) unless --dry-run.
set -euo pipefail
cd "$(dirname "$0")/.."

version="${1:?usage: .github/release-npm.sh <version> [--dry-run]}"
dry="${2:-}"
scope=@mcurcio
registry=https://npm.pkg.github.com
tarball="dist/release/knobly-$version.tgz"
[ -s "$tarball" ] || { echo "release-npm.sh: no $tarball (run .github/release-build.sh $version first)" >&2; exit 1; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
tar -xzf "$tarball" -C "$work"
# npm pack's tarball holds one folder, package/.
node -e '
  const fs = require("fs"), [file, scope, registry] = process.argv.slice(1);
  const pkg = JSON.parse(fs.readFileSync(file, "utf8"));
  if (pkg.name !== "knobly") throw new Error(`expected the package knobly, found ${pkg.name}`);
  pkg.name = `${scope}/knobly`;
  pkg.publishConfig = { registry };
  fs.writeFileSync(file, JSON.stringify(pkg, null, 2) + "\n");
' "$work/package/package.json" "$scope" "$registry"

cat > "$work/.npmrc" <<EOF
$scope:registry=$registry
//npm.pkg.github.com/:_authToken=\${NODE_AUTH_TOKEN}
EOF

if [ "$dry" = --dry-run ]; then
  (cd "$work/package" && NODE_AUTH_TOKEN="${NODE_AUTH_TOKEN:-dry-run}" npm publish --dry-run --userconfig "$work/.npmrc")
else
  [ -n "${NODE_AUTH_TOKEN:-}" ] || { echo "release-npm.sh: NODE_AUTH_TOKEN is not set" >&2; exit 1; }
  (cd "$work/package" && npm publish --userconfig "$work/.npmrc")
fi
