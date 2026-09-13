"""Start the web application. Checks execute through HTTP requests."""
import os
import runpy
from pathlib import Path

if __name__ == '__main__':
    os.environ.setdefault('USE_RELOADER', '0')
    runpy.run_path(str(Path(__file__).with_name('flask_app.py')), run_name='__main__')
