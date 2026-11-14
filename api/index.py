import os
import shutil
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database
from app.main import create_app

# Vercel serverless environment has a read-only filesystem except /tmp
TMP_DIR = Path("/tmp")
if TMP_DIR.exists() and os.access(TMP_DIR, os.W_OK):
    db_path = TMP_DIR / "signal.db"
    seed_db = ROOT / "data" / "signal.db"
    if not db_path.exists() and seed_db.exists():
        try:
            shutil.copyfile(seed_db, db_path)
        except Exception:
            db_path = seed_db
else:
    db_path = ROOT / "data" / "signal.db"

# Create app with scheduler disabled (serverless environments cannot run background daemons)
db = Database(db_path)
app = create_app(db, scheduler=False)
