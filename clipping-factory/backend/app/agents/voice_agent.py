"""
VoiceAgent — Synthesizes hyper-realistic voiceovers or conversational responses.
Can be used for YouTube Shorts (faceless channels) or real-time cold calling.
"""
import os
from app.agents.base_agent import AgentResult, BaseAgent
from app.services.ai_service import AIService
from google.genai import types

class VoiceAgent(BaseAgent):
    name = "voice_agent"

    def run(self, text_script: str, voice_style: str = "Puck") -> AgentResult:
        self.logger.info(f"Generating voice audio for script (style: {voice_style})")
        
        # Google Cloud Text-to-Speech (or Gemini 2.0 Audio output if supported)
        ai = AIService()
        client = ai._get_gemini()
        
        try:
            # We use Gemini's new audio synthesis capability (or fallback to a fast TTS API)
            # For this agent, we will structure it to request speech output using the gemini API
            config_kwargs = {
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": voice_style
                        }
                    }
                }
            }
            
            prompt = f"Read the following script with high energy and perfect pacing:\n\n{text_script}"
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs)
            )
            
            # Extract audio data (base64 encoded in response)
            # In a real pipeline, we'd save this to storage
            audio_path = "/tmp/generated_voice.mp3"
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and "audio" in part.inline_data.mime_type:
                        with open(audio_path, "wb") as f:
                            f.write(part.inline_data.data)
                        
                        self._audit("audio", "generated", "voice_synthesized", metadata={"style": voice_style})
                        return AgentResult.ok({"audio_path": audio_path, "style": voice_style})
            
            return AgentResult.fail("No audio data returned from Gemini")

        except Exception as exc:
            self.logger.error(f"Failed to generate voice: {exc}")
            return AgentResult.fail(f"Voice generation failed: {exc}")
