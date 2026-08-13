import logging
import json
import os
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ClippingSchedulerAgent:
    def __init__(self):
        self.queue_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "publish_queue")
        os.makedirs(self.queue_dir, exist_ok=True)
        logging.info("Initialized Clipping Auto-Scheduler Agent.")

    def schedule_clip(self, clip_metadata, channel="MBM_Main"):
        """
        Takes a finalized clip from the clipping factory and drops it into a scheduled publish slot.
        """
        logging.info(f"Scheduling clip {clip_metadata.get('id', 'UNKNOWN')} for {channel}")
        
        publish_time = datetime.now() + timedelta(hours=4)
        
        schedule_entry = {
            "clip_id": clip_metadata.get('id', 'temp_id'),
            "file_path": clip_metadata.get('path', ''),
            "channel": channel,
            "scheduled_time": publish_time.isoformat(),
            "status": "QUEUED"
        }
        
        output_file = os.path.join(self.queue_dir, f"schedule_{schedule_entry['clip_id']}.json")
        with open(output_file, 'w') as f:
            json.dump(schedule_entry, f, indent=2)
            
        logging.info(f"Clip scheduled successfully for {schedule_entry['scheduled_time']} at {output_file}")
        return output_file

if __name__ == "__main__":
    agent = ClippingSchedulerAgent()
    agent.schedule_clip({"id": "clip_448", "path": "/videos/clip_448_final.mp4"})
