import os
import json
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_top_shorts(theme, max_results=5):
    """Fetches top-performing shorts based on a theme keyword using RapidAPI (yt-api)."""
    if not RAPIDAPI_KEY:
        print("[PROMPT OPTIMIZER] No RAPIDAPI_KEY found, skipping benchmarks.")
        return []

    print(f"[PROMPT OPTIMIZER] Searching RapidAPI for top '{theme}' shorts...")
    search_url = "https://yt-api.p.rapidapi.com/search"
    params = {
        "query": f"{theme} #shorts",
    }
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "yt-api.p.rapidapi.com"
    }
    
    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        items = response.json().get("data", [])
        
        benchmarks = []
        for item in items:
            if item.get("type") != "video":
                continue
            title = item.get("title", "")
            desc = item.get("description", "")
            video_id = item.get("videoId", "")
            benchmarks.append({"title": title, "description": desc, "id": video_id})
            if len(benchmarks) >= max_results:
                break
        return benchmarks
    except Exception as e:
        print(f"[PROMPT OPTIMIZER] Error fetching from RapidAPI: {e}")
        return []

def optimize_prompt(brand_slug, theme, original_script, original_title, original_description):
    """Uses Gemini via web REST API to optimize the prompt based on benchmarks."""
    benchmarks = fetch_top_shorts(theme)
    
    if not GEMINI_API_KEY:
        print("[PROMPT OPTIMIZER] No GEMINI_API_KEY found. Returning original prompts.")
        return original_script, original_title, original_description

    system_instruction = (
        "You are a master YouTube Shorts copywriter. Your goal is to maximize engagement and watch time."
    )
    
    prompt = f"""
I need to optimize the script, title, and description for a YouTube Short.

Brand Theme: {theme}

Original Title: {original_title}
Original Description: {original_description}
Original Script:
{original_script}

Here are some top-performing Shorts in this niche as benchmarks:
"""
    for idx, b in enumerate(benchmarks):
        prompt += f"Benchmark {idx+1} Title: {b['title']}\n"
        
    prompt += """
Please rewrite the script, title, and description to be extremely compelling, high-retention, and clickable.
Keep the core facts of the story intact. The script is for an AI voiceover.
Respond strictly in JSON format with exactly three keys: "script", "title", "description". No markdown blocks or extra text.
"""

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }
    
    print(f"[PROMPT OPTIMIZER] Calling Gemini API to enhance prompts for '{brand_slug}'...")
    try:
        res = requests.post(gemini_url, json=payload, timeout=30)
        res.raise_for_status()
        response_data = res.json()
        
        text_content = response_data["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text_content)
        
        # Log the improvement
        log_dir = os.path.join(os.path.dirname(__file__), "generated_videos")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "prompt_improvement_log.txt")
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"--- {brand_slug} ---\n")
            f.write(f"Original Title: {original_title}\n")
            f.write(f"Improved Title: {result.get('title')}\n")
            f.write("\n")
            
        print(f"[PROMPT OPTIMIZER] Successfully enhanced prompts for '{brand_slug}'")
        return result.get("script", original_script), result.get("title", original_title), result.get("description", original_description)
    except Exception as e:
        print(f"[PROMPT OPTIMIZER] Error generating optimized prompt with Gemini: {e}")
        return original_script, original_title, original_description

if __name__ == "__main__":
    # Test execution
    s, t, d = optimize_prompt("test", "plot twists", "A guy found a box.", "The Box", "He opened it.")
    print("Script:", s)
    print("Title:", t)
    print("Desc:", d)
