#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
version="${1:-0.1.0~preview1}"
cpu="${2:-}"
arch="$(dpkg --print-architecture)"
case "$arch:$cpu" in arm64:|arm64:cortex-a72|arm64:cortex-a76|amd64:) ;; *) echo "Unsupported architecture/CPU"; exit 1;; esac
pin=d3189ed482ded880c128bf312941266c4fa5ceec
if [ ! -d NeuralAmpModelerCore ]; then git clone https://github.com/sdatkinson/NeuralAmpModelerCore.git; fi
git -C NeuralAmpModelerCore checkout --detach "$pin"
git -C NeuralAmpModelerCore submodule update --init --recursive
cmake -S rpi -B build-deb -DCMAKE_BUILD_TYPE=Release -DRPIT3K_CPU="$cpu"
cmake --build build-deb -j"${JOBS:-2}"
ctest --test-dir build-deb --output-on-failure
build-deb/rpit3k --bypass --verify
python3 rpi/hiz_test.py build-deb/rpit3k
root="$(mktemp -d)"
trap 'rm -rf "$root"' EXIT
install -Dm755 build-deb/rpit3k "$root/usr/lib/rpi-ton3k/build-rpi/rpit3k"
for f in server.py tonecloud.py web.html; do install -Dm644 "rpi/$f" "$root/usr/lib/rpi-ton3k/rpi/$f"; done
install -Dm644 packaging/rpi-ton3k.service "$root/usr/lib/systemd/system/rpi-ton3k.service"
install -Dm644 packaging/config "$root/etc/default/rpi-ton3k"
install -Dm644 LICENSE "$root/usr/share/doc/rpi-ton3k/copyright"
mkdir -p "$root/DEBIAN" dist
# All variants deliberately share the package name: only one can be installed.
cat > "$root/DEBIAN/control" <<EOF
Package: rpi-ton3k
Version: $version
Architecture: $arch
Maintainer: RPi-Ton3K contributors
Depends: python3, alsa-utils, libasound2t64, libstdc++6, libc6, systemd, adduser, ca-certificates
Section: sound
Priority: optional
Description: Native NAM guitar processor with browser control
 Experimental Debian 13 package; CPU target: ${cpu:-portable}.
EOF
for f in preinst postinst prerm postrm; do install -m755 "packaging/$f" "$root/DEBIAN/$f"; done
printf '/etc/default/rpi-ton3k\n' > "$root/DEBIAN/conffiles"
dpkg-deb --root-owner-group --build "$root" "dist/rpi-ton3k_${version}_${arch}${cpu:+-$cpu}.deb"
