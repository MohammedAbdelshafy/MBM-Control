"""
AdvancedEnhancingAgent — Uses AI Vision to dynamically determine FFmpeg video filters.
Instead of relying on hardcoded settings, this agent analyzes a sample frame 
using Gemini Vision and generates custom color grading, brightness, contrast, 
and sharpening parameters specific to the video's lighting conditions.
"""
from pathlib import Path
from app.agents.base_agent import AgentResult, BaseAgent
from app.services.ai_service import AIService
from google.genai import types

class AdvancedEnhancingAgent(BaseAgent):
    name = "advanced_enhancing_agent"

    def run(self, clip_id: str, sample_frame_path: str) -> AgentResult:
        self.logger.info(f"Running advanced AI enhancing analysis on clip {clip_id}")
        
        if not Path(sample_frame_path).exists():
            return AgentResult.fail(f"Sample frame not found: {sample_frame_path}")

        schema = {
            "type": "object",
            "properties": {
                "brightness": {"type": "number", "description": "Brightness adjustment (-1.0 to 1.0)"},
                "contrast": {"type": "number", "description": "Contrast adjustment (-2.0 to 2.0)"},
                "saturation": {"type": "number", "description": "Saturation adjustment (0.0 to 3.0)"},
                "sharpen": {"type": "boolean", "description": "Whether to apply sharpening"},
                "denoise": {"type": "boolean", "description": "Whether to apply noise reduction"},
                "reasoning": {"type": "string", "description": "Explanation for these specific settings based on the image"}
            },
            "required": ["brightness", "contrast", "saturation", "sharpen", "denoise", "reasoning"]
        }

        # Use the raw Gemini client from AIService for multimodal (image + text)
        ai = AIService()
        client = ai._get_gemini()
        
        try:
            # Upload the frame to Gemini
            image_file = client.files.upload(file=sample_frame_path)
            
            prompt = (
                "Analyze this video frame. I am about to run it through FFmpeg filters. "
                "Determine the optimal brightness, contrast, and saturation adjustments to make it look cinematic, high-quality, and visually striking. "
                "Also determine if sharpening or denoising is needed."
            )
            
            system = "You are a professional colorist and video editor. Return exactly the JSON schema requested."
            
            config_kwargs = {
                "response_mime_type": "application/json",
                "response_schema": schema,
                "system_instruction": system
            }
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[image_file, prompt],
                config=types.GenerateContentConfig(**config_kwargs)
            )
            
            import json
            if response.text:
                result = json.loads(response.text)
                self._audit("clip", clip_id, "advanced_enhancing_computed", metadata={"settings": result})
                return AgentResult.ok({"clip_id": clip_id, "enhancement_settings": result})
            else:
                return AgentResult.fail("AI returned empty response")
                
        except Exception as exc:
            self.logger.error(f"Failed to analyze frame: {exc}")
            return AgentResult.fail(f"Vision analysis failed: {exc}")
