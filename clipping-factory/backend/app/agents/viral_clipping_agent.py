"""
ViralClippingAgent — Identifies the most viral 10-20 second segments from a transcript.
Uses Gemini to find high-retention hooks and returns start/end timestamps.
"""
from app.agents.base_agent import AgentResult, BaseAgent
from app.services.ai_service import AIService

class ViralClippingAgent(BaseAgent):
    name = "viral_clipping_agent"

    def run(self, clip_id: str, transcript_text: str) -> AgentResult:
        self.logger.info(f"Running viral clipping analysis on clip {clip_id}")
        
        schema = {
            "type": "object",
            "properties": {
                "hooks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start_time": {"type": "number", "description": "Start time in seconds"},
                            "end_time": {"type": "number", "description": "End time in seconds"},
                            "reasoning": {"type": "string", "description": "Why this clip will go viral"}
                        },
                        "required": ["start_time", "end_time", "reasoning"]
                    }
                }
            },
            "required": ["hooks"]
        }

        prompt = f"Analyze this transcript and find the top 3 most viral, controversial, or engaging 10-20 second segments.\n\nTranscript: {transcript_text}"
        system = "You are a master TikTok and YouTube Shorts editor. Your goal is to maximize audience retention by picking the best hooks."

        ai = AIService()
        result = ai.complete_structured(prompt, schema=schema, system=system)

        if not result or "hooks" not in result:
            return AgentResult.fail("AI failed to extract viral hooks")

        self._audit("clip", clip_id, "viral_clipping_analysis", metadata={"hooks": result["hooks"]})
        
        return AgentResult.ok({"clip_id": clip_id, "hooks": result["hooks"]})
