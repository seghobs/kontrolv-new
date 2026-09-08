"""Local launcher: web and worker are independent processes."""
import os
import signal
import subprocess
import sys
from pathlib import Path

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    worker = subprocess.Popen([sys.executable, str(root / 'worker.py')], cwd=root, creationflags=flags)
    web = subprocess.Popen([sys.executable, str(root / 'flask_app.py')], cwd=root, env={**os.environ, 'USE_RELOADER':'0'})
    try:
        web.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in (web, worker):
            if process.poll() is None:
                if process is worker and os.name == 'nt':
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
