import time
import os
import sys

# Add path so we can import publisher and pipeline
sys.path.append(os.path.dirname(__file__))

import publisher
# try importing pipeline. If missing dependencies, we'll mock it for the daemon loop for now
try:
    import pipeline
except ImportError:
    pipeline = None

def log(msg):
    print(f"[SOCIAL DAEMON] {time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}")

def run_daemon():
    log("[SOCIAL DAEMON] Started. Watching for new clips to publish...")
    
    while True:
        try:
            # 1. Run Pipeline (if available) to generate new clips and draft packages
            if pipeline:
                log("Triggering MBM-Social Pipeline...")
                try:
                    # pipeline.run_end_to_end() # Requires configured campaign
                    pass
                except Exception as e:
                    log(f"Pipeline error: {e}")
            
            # 2. Check Publish Queue
            filepath, package = publisher.get_next_draft()
            
            if filepath:
                log(f"Found draft package: {filepath}")
                log(f"Attempting to publish: {package.get('title')}")
                
                # 3. Publish to YouTube
                success = publisher.upload_to_youtube(
                    package.get("video_path"), 
                    package.get("title"), 
                    package.get("description")
                )
                
                if success:
                    publisher.mark_published(filepath, package)
                    log("[SOCIAL DAEMON] Successfully published locally.")
                else:
                    log("[SOCIAL DAEMON] Direct upload deferred. Syncing to Cloud Storage Queue for 24/7 background publishing...")
                    
                # Always sync qualified clips to Cloud Queue for offline publishing continuity
                try:
                    from app.services.cloud_publishing_queue import CloudPublishingQueue
                    cq = CloudPublishingQueue()
                    cq.sync_qualified_clip_to_cloud(package.get("video_path", filepath), package)
                    log("[SOCIAL DAEMON] Synced package to Cloud Storage & DB Queue (24/7 Laptop-Offline Mode Active).")
                except Exception as sync_err:
                    log(f"[SOCIAL DAEMON] Cloud Sync Notice: {sync_err}")
            else:
                log("No pending drafts. Sleeping for 15 minutes...")
                
            # Sleep 15 mins before checking again
            time.sleep(15 * 60)
            
        except KeyboardInterrupt:
            log("Shutting down daemon...")
            break
        except Exception as e:
            log(f"Daemon encountered error: {e}. Retrying in 60s...")
            time.sleep(60)

if __name__ == "__main__":
    run_daemon()
