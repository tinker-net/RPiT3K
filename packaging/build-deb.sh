#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
packaging="$PWD/packaging"
dist="$PWD/dist"
version="${1:-0.1.0~preview1}"
cpu="${2:-}"
edition="${3:-general}"
arch="$(dpkg --print-architecture)"
case "$arch:$cpu:$edition" in
 arm64:cortex-a76:pisound) source_ref="${RPIT3K_SOURCE_REF:-$(git rev-parse HEAD)}"; package=rpi-ton3k-pisound ;;
 arm64::general|arm64:cortex-a72:general|arm64:cortex-a53:general|arm64:cortex-a76:general|amd64::general)
  source_ref="${RPIT3K_SOURCE_REF:-$(git rev-parse HEAD)}"; package=rpi-ton3k ;;
 *) echo "Unsupported architecture/CPU/edition"; exit 1 ;;
esac
work="$(mktemp -d)"
root="$work/root"
src="$work/source"
trap 'git worktree remove --force "$src" 2>/dev/null || true; rm -rf "$work"' EXIT
git fetch --no-tags origin "$source_ref"
git worktree add --detach "$src" "$source_ref"
pin=d3189ed482ded880c128bf312941266c4fa5ceec
git clone https://github.com/sdatkinson/NeuralAmpModelerCore.git "$src/NeuralAmpModelerCore"
git -C "$src/NeuralAmpModelerCore" checkout --detach "$pin"
git -C "$src/NeuralAmpModelerCore" submodule update --init --recursive
embedded="${RPIT3K_EMBEDDED_OVERRIDE:-OFF}"
if [[ -z "${RPIT3K_EMBEDDED_OVERRIDE:-}" && "$arch:$cpu" == arm64:cortex-a76 ]]; then embedded=ON; fi
[[ "$embedded" == ON || "$embedded" == OFF ]] || { echo "Invalid Embedded override"; exit 1; }
cmake -S "$src/rpi" -B "$src/build-rpi" -DCMAKE_BUILD_TYPE=Release -DRPIT3K_CPU="$cpu" -DRPIT3K_EMBEDDED="$embedded" -DCMAKE_BUILD_RPATH_USE_ORIGIN=ON
cmake --build "$src/build-rpi" -j"${JOBS:-2}"
ctest --test-dir "$src/build-rpi" --output-on-failure
"$src/build-rpi/rpit3k" --bypass --verify
python3 "$src/rpi/hiz_test.py" "$src/build-rpi/rpit3k"
prefix="$root/usr/lib/rpi-ton3k"
doc="$root/usr/share/doc/$package"
install -Dm755 "$src/build-rpi/rpit3k" "$prefix/build-rpi/rpit3k"
install -Dm755 "$src/build-rpi/librpit3k-daisysp.so" "$prefix/build-rpi/librpit3k-daisysp.so"
for f in server.py tonecloud.py calibration.py capture_info.py ir_info.py web.html; do install -Dm644 "$src/rpi/$f" "$prefix/rpi/$f"; done
{
 for f in practice.py data_backup.py; do install -Dm644 "$src/rpi/$f" "$prefix/rpi/$f"; done
 bash "$src/rpi/install-score-reader.sh"
 mkdir -p "$prefix/rpi/vendor"
 cp -a "$src/rpi/vendor/alphatab" "$prefix/rpi/vendor/"
 python3 - "$prefix/rpi/build-info.json" "$version" "$source_ref" "$edition" "$cpu" "$embedded" <<'PY'
import json,sys
with open(sys.argv[1],"w") as f:json.dump(dict(edition=("PiSound DEB" if sys.argv[4]=="pisound" else "General DEB"),version=sys.argv[2],commit=sys.argv[3],cpu=sys.argv[5] or "portable",embedded=sys.argv[6]),f)
PY
}
install -Dm644 "$src/LICENSE" "$doc/copyright"
install -Dm644 "$src/UI-TONE3000-LICENSE.txt" "$doc/UI-TONE3000-LICENSE.txt"
cp -a "$src/rpi/vendor/daisysp" "$doc/daisysp-source"
for f in LICENSE LICENSE.md LICENSE.txt; do if [[ -f "$src/NeuralAmpModelerCore/$f" ]]; then install -Dm644 "$src/NeuralAmpModelerCore/$f" "$doc/NAM-Core-$f"; fi; done
if [[ "$embedded" == ON ]]; then
 for f in LICENSE LICENSE.md LICENSE.txt; do if [[ -f "$src/build-rpi/_deps/t3kembedded-src/$f" ]]; then install -Dm644 "$src/build-rpi/_deps/t3kembedded-src/$f" "$doc/TONE3000-Embedded-$f"; fi; done
fi
printf 'source=%s\nNAM Core=%s\nCPU=%s\nEmbedded=%s\n' "$source_ref" "$pin" "${cpu:-portable}" "$embedded" > "$doc/build-provenance"
mkdir -p "$root/DEBIAN" "$dist"
depends="python3, alsa-utils, libasound2t64, libstdc++6, libc6, systemd, adduser, ca-certificates, ffmpeg, openssl, sudo, util-linux"
conflicts=rpi-ton3k-pisound
if [[ "$edition" == pisound ]]; then
 conflicts=rpi-ton3k
 depends="$depends, pisound, pisound-btn, network-manager, dnsmasq-base, curl"
 install -Dm644 "$packaging/pisound.service" "$root/usr/lib/systemd/system/$package.service"
 install -Dm644 "$packaging/pisound-config" "$root/etc/default/$package"
 install -Dm644 "$packaging/pisound-hotspot.service" "$root/usr/lib/systemd/system/rpi-ton3k-pisound-hotspot.service"
 install -Dm644 "$packaging/pisound-hotspot.timer" "$root/usr/lib/systemd/system/rpi-ton3k-pisound-hotspot.timer"
 install -Dm755 "$src/rpi/pisound-button.sh" "$prefix/pisound/rpit3k-button"
 for action in stomp next identify audio hotspot shutdown; do ln -s rpit3k-button "$prefix/pisound/rpit3k-button-$action"; done
 sed 's@/usr/local/bin/@/usr/lib/rpi-ton3k/pisound/@g' "$src/rpi/pisound-button.conf" > "$prefix/pisound/button.conf"
 install -Dm755 "$src/rpi/hotspot-check.sh" "$prefix/pisound/hotspot-check"
 install -Dm755 "$packaging/pisound-setup" "$prefix/pisound/setup"
 install -Dm755 "$packaging/pisound-postinst" "$root/DEBIAN/postinst"
 install -Dm755 "$packaging/pisound-prerm" "$root/DEBIAN/prerm"
 install -Dm755 "$packaging/pisound-postrm" "$root/DEBIAN/postrm"
else
 install -Dm644 "$packaging/rpi-ton3k.service" "$root/usr/lib/systemd/system/rpi-ton3k.service"
 install -Dm644 "$packaging/config" "$root/etc/default/rpi-ton3k"
 for f in postinst prerm postrm; do install -m755 "$packaging/$f" "$root/DEBIAN/$f"; done
fi
if [[ "$edition" == pisound ]]; then
 install -m755 "$packaging/pisound-preinst" "$root/DEBIAN/preinst"
else
 install -m755 "$packaging/preinst" "$root/DEBIAN/preinst"
fi
install -Dm644 "$src/rpi/release_update.py" "$prefix/rpi/release_update.py"
install -Dm755 "$packaging/update.py" "$prefix/update.py"
mkdir -p "$root/usr/lib/systemd/system"
sed "s/@PACKAGE@/$package/g" "$packaging/update.service" > "$root/usr/lib/systemd/system/rpi-ton3k-update.service"
if [[ -n "${TON3K_UPDATE_PUBLIC_KEY:-}" ]]; then
 mkdir -p "$root/usr/share/rpi-ton3k"
 printf '%s\n' "$TON3K_UPDATE_PUBLIC_KEY" > "$root/usr/share/rpi-ton3k/update-public.pem"
 openssl pkey -pubin -in "$root/usr/share/rpi-ton3k/update-public.pem" -noout
fi
cat > "$root/DEBIAN/control" <<EOF
Package: $package
Version: $version
Architecture: $arch
X-TON3K-CPU: ${cpu:-portable}
Maintainer: RPi-Ton3K contributors
Depends: $depends
Conflicts: $conflicts
Section: sound
Priority: optional
Description: Native NAM guitar processor ($edition edition)
 Experimental Debian 13 package; CPU target: ${cpu:-portable}.
EOF
printf '/etc/default/%s\n' "$package" > "$root/DEBIAN/conffiles"
# Verify the staged binary resolves its shared library outside the build directory.
"$prefix/build-rpi/rpit3k" --bypass --verify
python3 "$prefix/rpi/server.py" --help >/dev/null
if [[ "$edition" == general ]]; then
 test ! -e "$prefix/pisound"
 if [[ -n "$(find "$root" -iname '*pisound*' -print -quit)" ]]; then echo 'Unexpected Pisound payload in generic package' >&2; exit 1; fi
fi
dpkg-deb --root-owner-group --build "$root" "$dist/${package}_${version}_${arch}${cpu:+-$cpu}.deb"
