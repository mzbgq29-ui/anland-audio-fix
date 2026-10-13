from pathlib import Path
import collections
import hashlib
import json
import re
import subprocess
import tarfile

base = Path(__file__).parent
plans = [
    ('libpipewire', 'libpipewire-1:1.6.9-1-aarch64.pkg.tar.xz',
     'libpipewire-1:1.6.9-1.1-aarch64.pkg.tar.xz',
     'usr/lib/pipewire-0.3/libpipewire-module-client-device.so', 'pipewire-patched-library.so'),
    ('libwireplumber', 'libwireplumber-0.5.18-1-aarch64.pkg.tar.xz',
     'libwireplumber-0.5.18-1.1-aarch64.pkg.tar.xz',
     'usr/lib/libwireplumber-0.5.so.0.518.0', 'wireplumber-patched-library.so'),
]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_archive(path):
    payload = {}
    data = {}
    with tarfile.open(path, 'r|xz') as archive:
        for member in archive:
            content = archive.extractfile(member).read() if member.isfile() else None
            if member.name.startswith('.'):
                data[member.name] = content
                continue
            payload[member.name] = {
                field: (getattr(member, field).decode() if isinstance(getattr(member, field), bytes)
                        else getattr(member, field))
                for field in ('type', 'mode', 'uid', 'gid', 'uname', 'gname', 'mtime', 'linkname')
            }
            if content is not None:
                payload[member.name]['sha256'] = hashlib.sha256(content).hexdigest()
    metadata = collections.defaultdict(list)
    for line in data['.PKGINFO'].decode().splitlines():
        if ' = ' in line and not line.startswith('#'):
            key, value = line.split(' = ', 1)
            metadata[key].append(value)
    return payload, dict(metadata), data

reports = []
for name, original_name, patched_name, destination, staged_name in plans:
    original = base/'original'/original_name
    patched = base/'patched'/patched_name
    sig = original.with_name(original.name+'.sig')
    signature = subprocess.run(['gpgv', '--status-fd', '1', '--keyring',
                                '/etc/pacman.d/gnupg/pubring.gpg', str(sig), str(original)],
                               check=True, text=True, capture_output=True)
    assert 'VALIDSIG 68B3537F39A313B3E574D06777193F152BDBE6A6' in signature.stdout
    ap, am, ad = read_archive(original)
    bp, bm, bd = read_archive(patched)
    assert ap.keys() == bp.keys()
    differences = [path for path in ap if ap[path] != bp[path]]
    assert differences == [destination], differences
    before, after = dict(ap[destination]), dict(bp[destination])
    before.pop('sha256')
    after.pop('sha256')
    assert before == after
    assert bp[destination]['sha256'] == digest(base/'staging'/staged_name)
    changed_metadata = sorted(k for k in am.keys() | bm.keys() if am.get(k) != bm.get(k))
    assert changed_metadata == ['packager', 'pkgver', 'provides', 'size'], changed_metadata
    assert bm['pkgver'] == [am['pkgver'][0]+'.1']
    compatibility = name+'='+am['pkgver'][0]
    assert bm['provides'] == am['provides']+[compatibility]
    assert bm['packager'] == ['Local Anland audio root fix (unsigned local build)']
    assert ad.get('.INSTALL') == bd.get('.INSTALL')
    assert ad.get('.CHANGELOG') == bd.get('.CHANGELOG')
    dynamic = subprocess.check_output(['readelf', '-d', str(base/'staging'/staged_name)], text=True)
    assert '(RPATH)' not in dynamic and '(RUNPATH)' not in dynamic
    binary_strings = subprocess.check_output(['strings', str(base/'staging'/staged_name)], text=True)
    assert '/usr/local' not in binary_strings
    if name == 'libwireplumber':
        assert '/usr/lib\n' in binary_strings and '/etc\n' in binary_strings and '/usr/share\n' in binary_strings
    report = {
        'name': name,
        'original_package': str(original),
        'patched_package': str(patched),
        'original_sha256': digest(original),
        'patched_sha256': digest(patched),
        'signature_key': '68B3537F39A313B3E574D06777193F152BDBE6A6',
        'payload_entries': len(ap),
        'payload_regular_files': sum(x['type'] == '0' for x in ap.values()),
        'payload_symlinks': sum(x['type'] == '2' for x in ap.values()),
        'changed_payload_path': destination,
        'all_other_payload_and_all_entry_metadata_identical': True,
        'changed_pkginfo_fields': changed_metadata,
        'compatibility_provides': compatibility,
        'install_script': 'preserved' if ad.get('.INSTALL') else 'absent upstream',
        'build_runpath': 'absent',
        'usr_local_build_paths': 'absent',
        'installation_prefix': '/usr',
        'sysconfdir': '/etc',
        'localstatedir': '/var',
    }
    reports.append(report)
    print('PASS signature, metadata, full payload and symlinks:', name,
          f'({len(ap)} payload entries, only {destination} changed)')

command = ['pacman', '--config', str(base/'pacman-local-build.conf'), '-Up', '--print-format', '%n %v %l']
command += [x['patched_package'] for x in reports]
plan = subprocess.run(command, check=True, text=True, capture_output=True)
assert 'libpipewire 1:1.6.9-1.1 ' in plan.stdout
assert 'libwireplumber 0.5.18-1.1 ' in plan.stdout
result = {'packages': reports, 'pacman_print_plan': plan.stdout, 'pacman_print_warnings': plan.stderr}
(base/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
(base/'pacman-install-plan.txt').write_text(plan.stdout+plan.stderr)
sha_lines = [x['original_sha256']+'  original/'+Path(x['original_package']).name for x in reports]
sha_lines += [x['patched_sha256']+'  patched/'+Path(x['patched_package']).name for x in reports]
(base/'SHA256SUMS').write_text('\n'.join(sha_lines)+'\n')
print('PASS pacman -Up installation plan accepts both local packages together')
print(plan.stdout.strip())
