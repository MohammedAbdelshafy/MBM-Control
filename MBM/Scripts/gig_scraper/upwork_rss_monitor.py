import time
import requests
import xml.etree.ElementTree as ET

# Example Upwork RSS Feed URL (You can get this from an Upwork search)
# Format: https://www.upwork.com/ab/feed/jobs/rss?q=AI+Agent&sort=recency
RSS_FEED_URL = "https://www.upwork.com/ab/feed/jobs/rss?q=AI+Agent+OR+FastAPI+OR+Vapi&sort=recency"

def fetch_latest_jobs():
    print(f"Fetching latest AI jobs from RSS feed...")
    try:
        response = requests.get(RSS_FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            jobs = []
            for item in root.findall('./channel/item'):
                job = {
                    "title": item.find('title').text,
                    "link": item.find('link').text,
                    "description": item.find('description').text,
                    "pubDate": item.find('pubDate').text
                }
                jobs.append(job)
            return jobs
        else:
            print(f"Failed to fetch feed. Status Code: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching feed: {e}")
        return []

def main():
    seen_jobs = set()
    print("Starting Upwork Job Monitor...")
    
    # Run a simple loop to check for new jobs
    while True:
        jobs = fetch_latest_jobs()
        for job in jobs:
            if job["link"] not in seen_jobs:
                print("\n--- NEW JOB FOUND ---")
                print(f"Title: {job['title']}")
                print(f"Link: {job['link']}")
                print(f"Published: {job['pubDate']}")
                seen_jobs.add(job["link"])
                
                # Here we could trigger a Telegram notification or draft a proposal
                # telegram_notify.send_message(f"New Job: {job['title']}\n{job['link']}")
                
        time.sleep(300) # Check every 5 minutes

if __name__ == "__main__":
    # To run: python upwork_rss_monitor.py
    main()
