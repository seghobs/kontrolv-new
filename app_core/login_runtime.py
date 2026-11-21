"""Activate the optional, offline-built PythonAnywhere login dependency bundle."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import zipfile

_lock = threading.Lock()


def activate():
    root = Path(__file__).resolve().parent.parent
    archive = root / '.login-runtime.zip'
    if not archive.exists():
        return  # Normal installations use requirements.txt.
    with _lock:
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()[:20]
        directory = root / '.login-runtime' / digest
        marker = directory / '.ready'
        if not marker.exists():
            directory.parent.mkdir(exist_ok=True)
            # Cross-worker lock: extraction is published atomically only when complete.
            with open(directory.parent / 'install.lock', 'a+b') as handle:
                if os.name != 'nt':
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX)
                if not marker.exists():
                    with tempfile.TemporaryDirectory(dir=directory.parent) as temporary:
                        stage = Path(temporary) / 'site'; stage.mkdir()
                        with zipfile.ZipFile(archive) as bundle:
                            for entry in bundle.infolist():
                                if not (stage / entry.filename).resolve().is_relative_to(stage.resolve()):
                                    raise ValueError('Invalid login runtime archive path')
                            bundle.extractall(stage)
                        (stage / '.ready').write_text(digest)
                        stage.rename(directory)
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
