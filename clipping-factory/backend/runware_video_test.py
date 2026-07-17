import asyncio
import os
from dotenv import load_dotenv
from runware import Runware

load_dotenv()
API_KEY = os.environ.get("RUNWARE_API_KEY")

async def main():
    if not API_KEY:
        print("RUNWARE_API_KEY not set")
        return
    print("Connecting to Runware...")
    async with Runware(api_key=API_KEY, transport="rest") as client:
        print("Connected. Requesting image generation...")
        try:
            images = await client.run({
                "taskType": "imageInference",
                "model": "runware:101@1",
                "positivePrompt": "A cinematic, highly detailed shot of a futuristic sports car driving through a neon-lit cyberpunk city, 4k, photorealistic",
                "width": 854,
                "height": 480,
                "numberResults": 1,
            })
            for i in images:
                print(f"Generated Image URL: {i.imageURL}")
        except Exception as e:
            print("Error generating image:", e)

if __name__ == "__main__":
    asyncio.run(main())
