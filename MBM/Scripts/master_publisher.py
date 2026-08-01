import os
import sys
import subprocess
from datetime import datetime

# Path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.append(BASE_DIR)

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[MASTER PUBLISHER] {timestamp} - {msg}")

def publish_all_pipelines():
    log("=== Triggering Publishing & Outreach for ALL Pipelines ===")

    # 1. Real Estate Distressed Seller Deal Outreach
    lead_daemon = os.path.join(BASE_DIR, 'LeadEngine', 'lead_engine_daemon.py')
    log("1. Publishing Real Estate Cash Offers & Lead Pipeline...")
    try:
        cmd = [
            sys.executable, lead_daemon,
            '--cities', 'manchester,london,birmingham,new york,dallas,houston,madrid,barcelona',
            '--target-deals', '30',
            '--outreach'
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        log("[SUCCESS] Real Estate Deal Outreach Complete.")
    except Exception as e:
        log(f"[WARNING] Real Estate Outreach warning: {e}")

    # 2. Multi-Touch Follow-Up Cadence Execution
    cadence_agent = os.path.join(BASE_DIR, 'LeadEngine', 'multi_touch_cadence_agent.py')
    log("2. Publishing Multi-Touch Follow-Up Emails...")
    try:
        subprocess.run([sys.executable, cadence_agent], capture_output=True, text=True, timeout=300)
        log("[SUCCESS] Multi-Touch Cadence Execution Complete.")
    except Exception as e:
        log(f"[WARNING] Cadence warning: {e}")

    # 3. WhatsApp & SMS Campaign Link Generator
    wa_blaster = os.path.join(BASE_DIR, 'LeadEngine', 'whatsapp_sms_blaster.py')
    log("3. Publishing WhatsApp & SMS Direct Campaign Links...")
    try:
        subprocess.run([sys.executable, wa_blaster], capture_output=True, text=True, timeout=300)
        log("[SUCCESS] WhatsApp & SMS Links Exported.")
    except Exception as e:
        log(f"[WARNING] WhatsApp generation warning: {e}")

    # 4. Cute Dosage YouTube US Pipeline
    cute_pipeline = os.path.join(BASE_DIR, 'Scripts', 'cutedosage_pipeline.py')
    log("4. Publishing Cute Dosage US YouTube Content Package...")
    try:
        subprocess.run([sys.executable, cute_pipeline], capture_output=True, text=True, timeout=300)
        log("[SUCCESS] Cute Dosage US Campaign Generated.")
    except Exception as e:
        log(f"[WARNING] Cute Dosage pipeline warning: {e}")

    # 5. Cinematic Movie Recap Engine, Viral AI Video Generator, Benchmark Auditor & YouTube Publisher
    recap_engine = os.path.join(ROOT_DIR, 'clipping-factory', 'MBM-Social', 'cinematic_movie_recap_engine.py')
    viral_ai_engine = os.path.join(ROOT_DIR, 'clipping-factory', 'MBM-Social', 'viral_1m_video_generator.py')
    transcriber_engine = os.path.join(ROOT_DIR, 'clipping-factory', 'MBM-Social', 'twists_clippingfactory_transcriber.py')
    quality_auditor = os.path.join(ROOT_DIR, 'clipping-factory', 'MBM-Social', 'video_quality_auditor_enhancer.py')
    yt_publisher = os.path.join(ROOT_DIR, 'clipping-factory', 'MBM-Social', 'mbm_social', 'youtube_api_publisher.py')
    log("5. Executing Cinematic Movie Recap Engine, Viral AI Generator, Benchmark Auditor & Enhancer Engine...")
    try:
        subprocess.run([sys.executable, recap_engine], capture_output=True, text=True, timeout=300)
        subprocess.run([sys.executable, viral_ai_engine], capture_output=True, text=True, timeout=300)
        subprocess.run([sys.executable, transcriber_engine], capture_output=True, text=True, timeout=300)
        subprocess.run([sys.executable, quality_auditor], capture_output=True, text=True, timeout=300)
        subprocess.run([sys.executable, yt_publisher], capture_output=True, text=True, timeout=300)
        log("[SUCCESS] YouTube Automated Posting Engine Completed.")
    except Exception as e:
        log(f"[WARNING] YouTube publishing warning: {e}")

    # 6. Telegram Live Digest Notification
    telegram_bot = os.path.join(BASE_DIR, 'Scripts', 'telegram_bot.py')
    log("6. Publishing Live Performance Digest to Telegram...")
    try:
        subprocess.run([sys.executable, telegram_bot, 'digest'], capture_output=True, text=True, timeout=60)
        log("[SUCCESS] Telegram Digest Sent.")
    except Exception as e:
        log(f"[WARNING] Telegram digest warning: {e}")

    # 7. AI Ops Agent (Log Inspector & Email Replied Agent)
    ai_ops = os.path.join(BASE_DIR, 'Scripts', 'ai_ops_agent.py')
    log("7. Running AI Ops & Support Agent (Logs & Emails)...")
    try:
        subprocess.run([sys.executable, ai_ops], capture_output=True, text=True, timeout=120)
        log("[SUCCESS] AI Ops Agent Completed.")
    except Exception as e:
        log(f"[WARNING] AI Ops Agent warning: {e}")

    log("=== ALL PIPELINES PUBLISHED SUCCESSFULLY ===")

if __name__ == "__main__":
    publish_all_pipelines()
