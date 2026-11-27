#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
version=1.8.4
dest=vendor/alphatab
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
command -v npm >/dev/null || { echo "Install npm first: sudo apt install npm"; exit 1; }
npm pack "@coderline/alphatab@$version" --pack-destination "$tmp"
tar -xzf "$tmp"/*.tgz -C "$tmp"
test -s "$tmp/package/dist/alphaTab.min.js"
test -s "$tmp/package/dist/font/Bravura.woff2"
mkdir -p "$dest/font"
cp "$tmp/package/dist/alphaTab.min.js" "$dest/"
cp "$tmp/package/dist/font/"Bravura.* "$dest/font/"
find "$tmp/package" -maxdepth 1 -iname '*license*' -exec cp {} "$dest/" \;
echo "alphaTab $version installed locally."
