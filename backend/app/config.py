import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

# make the local `stud` package importable regardless of CWD
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DATA_DIR = Path(os.environ.get("STUD_SERVER_DATA", BACKEND_DIR / "data"))
REPOS_DIR = DATA_DIR / "repos"
DATABASE_PATH = DATA_DIR / "stud_server.db"
DATABASE_URL = os.environ.get("STUD_SERVER_DB_URL", f"sqlite:///{DATABASE_PATH}")

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPOS_DIR.mkdir(parents=True, exist_ok=True)
