import os, sys, time
from pathlib import Path

# Replicate build_one_clip.py's forced override
os.environ["DATABASE_URL"] = "postgresql+asyncpg://clipuser:clippass@localhost:5432/clipping_factory"
BACKEND = Path(__file__).parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

def mask(u):
    if not u: return u
    # mask password between ://user:pass@
    return u

try:
    from app.core.config import get_settings
    s = get_settings()
    print("ACTIVE database_url:", s.database_url.replace("://", "://").split("@")[0] + "@(masked)")
except Exception as e:
    print("settings error:", e)

# TCP probe localhost:5432
import socket
ok = False
try:
    sock = socket.create_connection(("localhost", 5432), timeout=5)
    ok = True
    sock.close()
except Exception as e:
    print("TCP localhost:5432 ->", type(e).__name__, str(e)[:120])
print("TCP localhost:5432 reachable:", ok)

# Now try a sync query with a hard timeout via a thread
import threading
result = {}
def worker():
    try:
        from app.core.database import SyncSessionLocal
        from app.models.campaign import Campaign
        db = SyncSessionLocal()
        n = db.query(Campaign).count()
        db.close()
        result["n"] = n
        result["status"] = "OK"
    except Exception as e:
        result["status"] = "ERR"
        result["err"] = type(e).__name__ + ": " + str(e)[:300]
t = threading.Thread(target=worker, daemon=True)
t.start()
t.join(timeout=20)
if t.is_alive():
    print("DB CONNECT HUNG (no response in 20s) -- this is the build_one_clip hang")
else:
    print("DB result:", result)
