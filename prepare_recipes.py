from pathlib import Path
import collections
import hashlib
import shlex
import shutil
import tarfile

base = Path(__file__).parent
packages = [
    ('libpipewire', 'libpipewire-1:1.6.9-1-aarch64.pkg.tar.xz',
     'pipewire-patched-library.so', 'usr/lib/pipewire-0.3/libpipewire-module-client-device.so'),
    ('libwireplumber', 'libwireplumber-0.5.18-1-aarch64.pkg.tar.xz',
     'wireplumber-patched-library.so', 'usr/lib/libwireplumber-0.5.so.0.518.0'),
]

def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

mapping = {
    'license': 'license', 'depend': 'depends', 'optdepend': 'optdepends',
    'provides': 'provides', 'conflict': 'conflicts', 'replaces': 'replaces',
    'group': 'groups', 'backup': 'backup', 'makedepend': 'makedepends',
    'checkdepend': 'checkdepends',
}

for name, archive_name, patched_name, destination in packages:
    archive = base/'original'/archive_name
    recipe_dir = base/'recipes'/name
    recipe_dir.mkdir(exist_ok=True)
    with tarfile.open(archive) as upstream:
        text = upstream.extractfile('.PKGINFO').read().decode()
        metadata = collections.defaultdict(list)
        for line in text.splitlines():
            if ' = ' in line and not line.startswith('#'):
                key, value = line.split(' = ', 1)
                metadata[key].append(value)
        for script, variable in [('.INSTALL', 'install'), ('.CHANGELOG', 'changelog')]:
            member = next((m for m in upstream.getmembers() if m.name == script), None)
            if member:
                (recipe_dir/f'upstream{script.lower()}').write_bytes(upstream.extractfile(member).read())
        assert upstream.getmember(destination).isfile()

    original_link = recipe_dir/archive_name
    if original_link.is_symlink():
        original_link.unlink()
    original_link.symlink_to(archive)
    patched = recipe_dir/'patched-library.so'
    shutil.copy2(base/'staging'/patched_name, patched)
    patched.chmod(0o755)

    version = metadata['pkgver'][0].rsplit('-', 1)[0]
    epoch, version = version.split(':', 1) if ':' in version else ('0', version)
    lines = [
        '# Local Anland audio root-fix package, built by makepkg; NOT an official package.',
        '# The original signed Arch Linux ARM archive is retained separately for rollback.',
        '# Its payload is preserved byte for byte except for the one stated library.',
        f'pkgname={shlex.quote(name)}',
        f'pkgbase={shlex.quote(metadata["pkgbase"][0])}',
        f'pkgver={shlex.quote(version)}', 'pkgrel=1.1', f'epoch={epoch}',
        f'pkgdesc={shlex.quote(metadata["pkgdesc"][0])}',
        f'url={shlex.quote(metadata["url"][0])}',
        'arch=(' + ' '.join(map(shlex.quote, metadata['arch'])) + ')',
        '# This rebuild retains the single library member of the upstream split package.',
        'pkgtype=split',
        '# Keep upstream payload mtimes; local provenance is recorded in version and packager.',
        f'export SOURCE_DATE_EPOCH={metadata["builddate"][0]}',
        "PACKAGER='Local Anland audio root fix (unsigned local build)'",
    ]
    for source_key, recipe_key in mapping.items():
        if metadata[source_key]:
            lines.append(recipe_key+'=('+' '.join(map(shlex.quote, metadata[source_key]))+')')
    # Unchanged-ABI upstream split packages require the exact baseline library version.
    # Preserve that relationship while using a distinct local package release.
    lines += [
        '# Same upstream ABI: satisfy exact baseline dependencies from the sibling packages.',
        'provides+=(' + shlex.quote(name+'='+metadata['pkgver'][0]) + ')',
    ]
    for script, variable in [('.INSTALL', 'install'), ('.CHANGELOG', 'changelog')]:
        preserved = recipe_dir/f'upstream{script.lower()}'
        if preserved.is_file():
            lines.append(f'{variable}={shlex.quote(preserved.name)}')
    lines += [
        '# Disable transformations of all upstream files; only the replacement is stripped.',
        "options=('!strip' 'docs' 'libtool' 'staticlibs' 'emptydirs' '!zipman' '!purge' '!debug' '!lto')",
        f'_upstream_archive={shlex.quote(archive_name)}',
        f'_replacement_path={shlex.quote(destination)}',
        'source=("$_upstream_archive" \'patched-library.so\')',
        'noextract=("$_upstream_archive")',
        f'sha256sums=({shlex.quote(checksum(archive))} {shlex.quote(checksum(patched))})',
        '',
        'package() {',
        '  bsdtar -xpf "$srcdir/$_upstream_archive" -C "$pkgdir" \\',
        "    --exclude='.PKGINFO' --exclude='.BUILDINFO' --exclude='.MTREE' \\",
        "    --exclude='.INSTALL' --exclude='.CHANGELOG'",
        '  install -m755 "$srcdir/patched-library.so" "$pkgdir/$_replacement_path"',
        '}',
        '',
    ]
    recipe = recipe_dir/'PKGBUILD'
    recipe.write_text('\n'.join(lines))
    (recipe_dir/'UPSTREAM-PKGINFO').write_text(text)
    print('Generated', recipe)
