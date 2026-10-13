#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
cd "$(dirname "$0")"
if [[ ${1:-} != inside ]]; then
  [[ $(uname -m) == aarch64 ]] || { echo 'Use a native ARM64 Linux runner.' >&2; exit 1; }
  mkdir -p .cloud-work artifacts
  curl --fail --location --retry 3 --proto '=https' \
    https://de3.mirror.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz \
    -o .cloud-work/arch-rootfs.tar.gz
  sha256sum .cloud-work/arch-rootfs.tar.gz > artifacts/ROOTFS-SHA256SUMS
  docker import .cloud-work/arch-rootfs.tar.gz anland-arch-arm:local
  docker run --rm -v "$PWD:/repo" -w /repo anland-arch-arm:local \
    /bin/bash /repo/cloud-build.sh inside
  exit
fi

[[ $(uname -m) == aarch64 ]]
printf 'Server = https://de3.mirror.archlinuxarm.org/$arch/$repo\n' > /etc/pacman.d/mirrorlist
pacman-key --init
pacman-key --populate archlinuxarm
pacman --disable-sandbox-filesystem -Syu --noconfirm --needed base-devel meson ninja python git curl \
  glib2-devel libpipewire pipewire pipewire-audio wireplumber libwireplumber \
  lua pkgconf patchelf
printf "\nPKGEXT='.pkg.tar.xz'\n" >> /etc/makepkg.conf
# Companion daemon and development files must match this release baseline.
[[ $(pacman -Q libpipewire) == 'libpipewire 1:1.6.9-1' ]]
[[ $(pacman -Q libwireplumber) == 'libwireplumber 0.5.18-1' ]]

base=$PWD/.cloud-work
mkdir -p "$base"/{original,staging,recipes,patched,sources}
curl --fail --location --retry 3 --proto '=https' \
  https://codeload.github.com/PipeWire/pipewire/tar.gz/refs/tags/1.6.9 \
  -o "$base/sources/pipewire.tar.gz"
curl --fail --location --retry 3 --proto '=https' \
  https://codeload.github.com/PipeWire/wireplumber/tar.gz/refs/tags/0.5.18 \
  -o "$base/sources/wireplumber.tar.gz"
printf '%s  %s\n' \
  dbc3624cf71215c26a22fc98f6f71f7b8599f5f6b415eab4a5c90ca96c170c7c "$base/sources/pipewire.tar.gz" \
  8c8a326a5b2a570681c1503c83f1fce0cc54ba862019815604b2bc92a7d483a1 "$base/sources/wireplumber.tar.gz" \
  | sha256sum -c -
tar -xf "$base/sources/pipewire.tar.gz" -C "$base/sources"
tar -xf "$base/sources/wireplumber.tar.gz" -C "$base/sources"
patch --batch --fuzz=0 -p1 -d "$base/sources/pipewire-1.6.9" < pipewire-listener-error.patch
patch --batch --fuzz=0 -p1 -d "$base/sources/wireplumber-0.5.18" < wireplumber-device-export-error.patch

meson setup "$base/sources/pipewire-1.6.9/build" "$base/sources/pipewire-1.6.9" \
  --prefix=/usr --libdir=lib --sysconfdir=/etc --localstatedir=/var \
  -Dauto_features=disabled -Dspa-plugins=enabled -Dsupport=enabled \
  -Dbluez5=disabled -Dalsa=disabled -Dv4l2=disabled -Dsession-managers=[] \
  -Ddocs=disabled -Dman=disabled -Dtests=disabled -Dexamples=disabled \
  -Dsystemd-system-service=disabled -Dsystemd-user-service=disabled
ninja -C "$base/sources/pipewire-1.6.9/build" src/modules/libpipewire-module-client-device.so
meson setup "$base/sources/wireplumber-0.5.18/build" "$base/sources/wireplumber-0.5.18" \
  --prefix=/usr --libdir=lib --sysconfdir=/etc --localstatedir=/var \
  -Ddoc=disabled -Dintrospection=disabled -Ddaemon=false -Dmodules=false \
  -Dtools=false -Dtests=true -Ddbus-tests=false -Dsystem-lua-version=5.4
ninja -C "$base/sources/wireplumber-0.5.18/build" lib/wp/libwireplumber-0.5.so.0.518.0
cp "$base/sources/pipewire-1.6.9/build/src/modules/libpipewire-module-client-device.so" \
  "$base/staging/pipewire-patched-library.so"
cp "$base/sources/wireplumber-0.5.18/build/lib/wp/libwireplumber-0.5.so.0.518.0" \
  "$base/staging/wireplumber-patched-library.so"
for file in "$base"/staging/*.so; do
  patchelf --remove-rpath "$file"
  strip --strip-unneeded "$file"
done

for name in 'libpipewire-1:1.6.9-1-aarch64.pkg.tar.xz' 'libwireplumber-0.5.18-1-aarch64.pkg.tar.xz'; do
  curl --fail --location --retry 3 --proto '=https' \
    "https://de3.mirror.archlinuxarm.org/aarch64/extra/$name" -o "$base/original/$name"
  curl --fail --location --retry 3 --proto '=https' \
    "https://de3.mirror.archlinuxarm.org/aarch64/extra/$name.sig" -o "$base/original/$name.sig"
done
printf '%s  %s\n' \
  21e81a38ea0217e0b0675b00c1c98bb547098f00d689201a27c34824e442d66e "$base/original/libpipewire-1:1.6.9-1-aarch64.pkg.tar.xz" \
  9fc7aedc4079fadbef1fd7079076b781bee45431d9e534b7c45b82c39ad17d9c "$base/original/libwireplumber-0.5.18-1-aarch64.pkg.tar.xz" \
  | sha256sum -c -
for archive in "$base"/original/*.pkg.tar.xz; do
  gpgv --keyring /etc/pacman.d/gnupg/pubring.gpg "$archive.sig" "$archive"
done
cp prepare_recipes.py verify_packages.py "$base/"
python "$base/prepare_recipes.py"
useradd --create-home builder
chown -R builder:builder "$base"
for name in libpipewire libwireplumber; do
  runuser -u builder -- /bin/bash -c 'cd "$1"; makepkg --nodeps --noconfirm --force' \
    bash "$base/recipes/$name"
  cp "$base/recipes/$name"/*.pkg.tar.xz "$base/patched/"
done
python - "$base" <<'PY'
from pathlib import Path
import re,sys
base=Path(sys.argv[1])
text=Path('/etc/pacman.conf').read_text()
text,count=re.subn(r'(?m)^\s*#?\s*LocalFileSigLevel\s*=.*$', 'LocalFileSigLevel = Optional', text)
if not count:
    text=text.replace('[options]\n','[options]\nLocalFileSigLevel = Optional\n',1)
(base/'pacman-local-build.conf').write_text(text)
PY
python "$base/verify_packages.py"
python - <<'PY'
import zipfile
with zipfile.ZipFile('anland-audio-PR-materials.zip') as z:
    z.extractall('.cloud-work/review')
PY
python "$base/review/upstream-root-fixes/run-regressions.py" \
  --patched-module-dir "$base/sources/pipewire-1.6.9/build/src/modules:/usr/lib/pipewire-0.3" \
  --patched-wp-lib-dir "$base/sources/wireplumber-0.5.18/build/lib/wp" \
  --output-dir "$base/regression-results"
git init "$base/anland"
git -C "$base/anland" remote add origin https://github.com/SuperTurtleDev/anland.git
git -C "$base/anland" fetch --depth=1 origin a271f010b0f2ed413e193e779e38daa77070c974
git -C "$base/anland" checkout --detach FETCH_HEAD
git -C "$base/anland" apply --check /repo/anland-audio-fix.patch
git -C "$base/anland" apply /repo/anland-audio-fix.patch
(cd "$base/anland"; python -m unittest discover -s libdisplay_producer/wireplumber/tests -v) \
  > "$base/regression-results/anland-tests.log" 2>&1
pacman -Q > artifacts/BUILD-ENVIRONMENT.txt
cp -a "$base"/{original,patched,SHA256SUMS,verification.json,regression-results} artifacts/
cp 50-anland-android-camera.conf INSTALL.md FIX_DETAILS.md artifacts/
echo 'PASS: native ARM64 builds, upstream signatures, package payload checks and isolated regressions'

# Artifact uploads reject colons in epoch-versioned pacman filenames.
# Preserve the exact package names inside a portable tar archive.
tar -czf "$base/anland-audio-archlinuxarm-aarch64.tar.gz" -C artifacts .
mv artifacts "$base/expanded-artifacts"
mkdir artifacts
cp "$base/anland-audio-archlinuxarm-aarch64.tar.gz" artifacts/
