"""Point the test suite at a throwaway SQLite database.

This has to run before any test module imports `database`, because the engine
is built at import time from DATABASE_URL. A test that set the variable in its
own module body was too late whenever pytest had already imported another
module that pulled `database` in first, and the suite then tried to create
tables against the real MySQL URL.

conftest.py is imported by pytest ahead of the test modules, which is the only
reliable place to do this.
"""
import os
import pathlib
import sys
import tempfile

_APP_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

_DB_PATH = pathlib.Path(tempfile.gettempdir()) / "plagsini_test_suite.db"
if _DB_PATH.exists():
    try:
        _DB_PATH.unlink()
    except OSError:
        # Windows keeps a handle open if a previous run crashed mid-connection.
        # Reusing the file is fine: every table is created fresh below.
        pass

os.environ["DATABASE_URL"] = "sqlite:///" + _DB_PATH.as_posix()
os.environ.setdefault("OCPI_TOKEN", "test-token")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-tests-only")
os.environ.setdefault("APP_ENV", "development")
