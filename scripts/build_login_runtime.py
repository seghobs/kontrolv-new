"""Build an offline CPython 3.13/Linux login dependency bundle for PythonAnywhere.

Usage: python scripts/build_login_runtime.py --output scratch/login-runtime.zip
The archive contains public dependencies only, never local sessions or profiles.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

REV = '62f962e3dba41d43237061635d2946ac93cc5be0'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args(); output=Path(args.output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary); wheels=root/'wheels';wheels.mkdir()
        subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--wheel-dir',str(wheels),
            'https://github.com/subzeroid/instagrapi/archive/'+REV+'.zip'],check=True)
        sdk=next(wheels.glob('instagrapi-*.whl'))
        subprocess.run([sys.executable,'-m','pip','download','--only-binary=:all:',
            '--platform','manylinux_2_17_x86_64','--platform','manylinux_2_28_x86_64',
            '--python-version','313','--implementation','cp','--abi','cp313',
            '--dest',str(wheels),str(sdk)],check=True)
        site=root/'site';site.mkdir()
        for wheel in wheels.glob('*.whl'):
            with zipfile.ZipFile(wheel) as archive:
                for entry in archive.infolist():
                    path=entry.filename
                    if '.data/purelib/' in path:path=path.split('.data/purelib/',1)[1]
                    if '.data/platlib/' in path:path=path.split('.data/platlib/',1)[1]
                    target=(site/path).resolve()
                    if not target.is_relative_to(site):raise ValueError('Invalid wheel path')
                    if not entry.is_dir():
                        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(entry))
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(site.rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(site))
        print('Built',output,output.stat().st_size,'bytes')


if __name__=='__main__':main()
