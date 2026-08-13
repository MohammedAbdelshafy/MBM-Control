"""
MarketingAgent — Generates highly optimized marketing copy for video clips.
Uses Gemini to generate SEO-optimized titles, YouTube/TikTok descriptions, 
and promotional tweets based on the clip's transcript and niche.
"""
from app.agents.base_agent import AgentResult, BaseAgent
from app.services.ai_service import AIService

class MarketingAgent(BaseAgent):
    name = "marketing_agent"

    def run(self, clip_id: str, transcript_text: str, niche: str = "general") -> AgentResult:
        self.logger.info(f"Generating marketing copy for clip {clip_id} (niche: {niche})")
        
        schema = {
            "type": "object",
            "properties": {
                "youtube_title": {"type": "string", "description": "High CTR YouTube Title"},
                "youtube_description": {"type": "string", "description": "SEO optimized YouTube description with hashtags"},
                "tiktok_caption": {"type": "string", "description": "Short, punchy TikTok caption with trending hashtags"},
                "promotional_tweet": {"type": "string", "description": "A viral-style tweet promoting the video link"}
            },
            "required": ["youtube_title", "youtube_description", "tiktok_caption", "promotional_tweet"]
        }

        prompt = (
            f"Generate viral marketing copy for a short-form video in the '{niche}' niche.\n\n"
            f"Transcript of the video:\n{transcript_text}\n\n"
            f"Provide the exact JSON schema requested."
        )
        
        system = (
            "You are an elite social media manager and YouTube growth expert. "
            "Your copy is punchy, curiosity-inducing, and SEO-optimized to maximize click-through-rates and algorithm distribution."
        )

        ai = AIService()
        result = ai.complete_structured(prompt, schema=schema, system=system)

        if not result:
            return AgentResult.fail("AI failed to generate marketing copy")

        self._audit("clip", clip_id, "marketing_copy_generated", metadata={"marketing_data": result})
        
        return AgentResult.ok({"clip_id": clip_id, "marketing": result})
