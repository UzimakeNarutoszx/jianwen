"""Remove unused runtime permissions from a cloud APK, then sign with its release key.

The cloud original is retained. HBuilderX's safe pack currently retains these
permissions despite excludePermissions/tools:node, so verify the final artifact.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--sdk', type=Path, required=True)
parser.add_argument('--hbuilder', type=Path, required=True)
parser.add_argument('--signing-dir', type=Path, required=True)
args = parser.parse_args()
source = args.source.resolve()
output = args.output.resolve()
if source == output:
    raise SystemExit('Keep the original cloud APK separate.')
output.parent.mkdir(parents=True, exist_ok=True)
java_home = Path(os.environ['JAVA_HOME'])
java = str(java_home / 'bin/java')
build = args.sdk / 'build-tools/36.0.0'
apktool = args.hbuilder / 'Contents/HBuilderX/plugins/app-safe-pack/apktool.jar'
removed = {
    'android.permission.INSTALL_PACKAGES',
    'android.permission.REQUEST_INSTALL_PACKAGES',
    'android.permission.READ_MEDIA_VIDEO',
    'com.asus.msa.SupplementaryDID.ACCESS',
    'com.huawei.android.launcher.permission.CHANGE_BADGE',
    'com.vivo.notification.permission.BADGE_ICON',
}

def run(*command):
    subprocess.run([str(part) for part in command], check=True)

with tempfile.TemporaryDirectory(prefix='jianwen-release-') as temp:
    root = Path(temp)
    decoded = root / 'decoded'
    run(java, '-jar', apktool, 'd', '-s', '-f', source, '-o', decoded)
    manifest = decoded / 'AndroidManifest.xml'
    tree = ET.parse(manifest)
    android = '{http://schemas.android.com/apk/res/android}'
    for node in list(tree.getroot()):
        if node.tag == 'uses-permission' and node.get(android + 'name') in removed:
            tree.getroot().remove(node)
    ET.register_namespace('android', android[1:-1])
    tree.write(manifest, encoding='utf-8', xml_declaration=True)
    run(java, '-jar', apktool, 'b', decoded, '-o', root / 'unsigned.apk')
    run(build / 'zipalign', '-f', '-P', '16', '4', root / 'unsigned.apk', root / 'aligned.apk')
    run(build / 'apksigner', 'sign', '--ks', args.signing_dir / 'jianwen-release.keystore',
        '--ks-key-alias', 'jianwen-release', '--ks-pass',
        'file:' + str(args.signing_dir / 'release-password.txt'),
        '--out', output, root / 'aligned.apk')

run(build / 'apksigner', 'verify', '--verbose', '--print-certs', output)
permissions = subprocess.check_output([str(build / 'aapt'), 'dump', 'permissions', str(output)], text=True)
for permission in removed:
    if "name='" + permission + "'" in permissions:
        raise SystemExit('Unexpected permission retained: ' + permission)
# App code and assets must be unchanged by manifest cleanup and re-signing.
with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
    for name in before.namelist():
        if name.startswith(('assets/', 'lib/')) or name.endswith('.dex'):
            if before.read(name) != after.read(name):
                raise SystemExit('App payload changed: ' + name)
print('Verified: signature, permission cleanup, unchanged app code/assets/native libraries.')
