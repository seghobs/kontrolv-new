"""Use this as the PythonAnywhere Web tab's WSGI application module."""
import os
os.environ['APP_DB_BACKEND'] = 'sqlite'
os.environ['APP_DB_FILE'] = '/home/kontrolyeni/mysite/app-sqlite.db'
os.environ.setdefault('APP_ENV', 'prod')
from flask_app import app as application
