"""Check draft packages for clippingfactorymbm."""
import json
import os

queue_dir = "publish_queue"
count = 0
for f in os.listdir(queue_dir):
    if f.endswith(".json"):
        try:
            d = json.loads(open(os.path.join(queue_dir, f), encoding="utf-8").read())
            if isinstance(d, dict) and d.get("status") == "draft" and d.get("brand") == "clippingfactorymbm":
                count += 1
                title = d.get("title", "no title")
                print(f"{f}: {title}")
        except Exception:
            pass
print(f"Total draft packages for clippingfactorymbm: {count}")
