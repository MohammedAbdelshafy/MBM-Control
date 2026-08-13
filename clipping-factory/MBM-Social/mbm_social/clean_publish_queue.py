import os
from pathlib import Path
from glob import glob

QUEUE_DIR = Path(__file__).resolve().parent.parent / "publish_queue"

def clean():
    if not QUEUE_DIR.exists():
        print(f"Queue directory not found: {QUEUE_DIR}")
        return

    files = glob(str(QUEUE_DIR / "*.json"))
    print(f"Found {len(files)} files in {QUEUE_DIR}. Deleting...")
    
    count = 0
    for f in files:
        try:
            os.remove(f)
            count += 1
        except Exception as e:
            print(f"Failed to delete {f}: {e}")
            
    print(f"Successfully deleted {count} junk files.")

if __name__ == "__main__":
    clean()
