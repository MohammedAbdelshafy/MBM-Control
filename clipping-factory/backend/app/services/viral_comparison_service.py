"""
ViralComparisonService — compares video clips against top-performing viral video benchmarks.

Evaluates 4 core dimensions:
1. Content & Story Arc Alignment
2. Opening 3s Hook Impact & Retention
3. Tag & SEO Keyword Coverage
4. Pacing & Structural Framing

Generates:
- Comprehensive Viral Comparison Report & Tier Score (A+, A, B, C)
- Enhanced Viral Tags & Hashtag Suite
- Rewritten Viral Hooks & Titles
- Multi-Platform Metadata Package (YouTube Shorts, TikTok, Reels, X)
- Benchmark-driven editing directives
"""
from typing import Any
import re
from app.services.ai_service import AIService
from app.core.logging_config import get_logger

logger = get_logger("services.viral_comparison")

# Default Viral Benchmark Profiles by Niche
BENCHMARK_PROFILES = {
    "general_viral": {
        "niche": "General Viral Shorts",
        "target_wpm": (140, 185),
        "ideal_duration": (25.0, 58.0),
        "hook_types": ["question", "bold_claim", "pattern_interrupt", "visual_shock"],
        "top_tags": ["#shorts", "#viral", "#trending", "#foryou", "#fyp", "viral moments", "top clips", "must watch"],
        "title_formulas": [
            "Why {Topic} Will Change Everything",
            "The Secret Behind {Topic} Nobody Talks About",
            "{Topic} Exposed: What You Never Knew",
            "This 1 Thing About {Topic} Changes Everything"
        ],
        "engagement_triggers": ["curiosity_gap", "emotional_peak", "revelation", "actionable_takeaway"]
    },
    "islamic_dawah": {
        "niche": "Islamic & Dawah Content",
        "target_wpm": (120, 160),
        "ideal_duration": (30.0, 60.0),
        "hook_types": ["spiritual_reminder", "quran_hadith_insight", "life_revelation", "heart_touching"],
        "top_tags": [
            "#islam", "#muslim", "#quran", "#dawah", "#islamicreminder", "#sunnah",
            "#muftimenk", "#noumanalikhan", "#omarsuleiman", "#allah", "#jannah",
            "#islamicstatus", "#shorts", "#viral"
        ],
        "title_formulas": [
            "Do NOT Ignore This Powerful Reminder about {Topic}",
            "This Will Soften Your Heart: {Topic}",
            "The Truth About {Topic} in Islam",
            "Never Forget This When You Feel {Topic}"
        ],
        "engagement_triggers": ["spiritual_reflection", "emotional_peak", "divine_wisdom", "practical_advice"]
    },
    "business_finance": {
        "niche": "Business, Money & Tech",
        "target_wpm": (150, 190),
        "ideal_duration": (20.0, 50.0),
        "hook_types": ["stat_reveal", "financial_secret", "mistake_to_avoid", "framework"],
        "top_tags": [
            "#business", "#entrepreneur", "#money", "#finance", "#wealth", "#startup",
            "#tech", "#productivity", "#mindset", "#shorts", "#viral"
        ],
        "title_formulas": [
            "How {Topic} Makes Millions Every Single Month",
            "Stop Doing This If You Want To Master {Topic}",
            "The 3-Step Framework For {Topic}",
            "How To Scale {Topic} Fast"
        ],
        "engagement_triggers": ["actionable_tip", "financial_gain", "productivity_hack", "insider_knowledge"]
    },
    "real_estate_wholesaling": {
        "niche": "Real Estate Wholesaling & Contract Structure",
        "target_wpm": (145, 185),
        "ideal_duration": (20.0, 50.0),
        "hook_types": ["contract_secret", "assignment_fee_reveal", "seller_objection", "no_money_deal"],
        "top_tags": [
            "#realestate", "#wholesaling", "#wholesalingrealestate", "#realestateinvesting",
            "#assignmentcontract", "#propertydeals", "#cashbuyers", "#distressedproperties",
            "#entrepreneur", "#shorts", "#viral"
        ],
        "title_formulas": [
            "How To Close A $10,000 Wholesaling Contract With $0 Down",
            "The #1 Clause Every Wholesaling Contract MUST Have",
            "How To Assign Real Estate Contracts Legally & Fast",
            "The Secret To Finding Cash Buyers For Wholesaling Deals"
        ],
        "engagement_triggers": ["contract_clause", "assignment_fee", "no_money_down", "deal_walkthrough"]
    },
    "tech_ai": {
        "niche": "AI, Software & Future Tech",
        "target_wpm": (150, 195),
        "ideal_duration": (25.0, 55.0),
        "hook_types": ["tool_showcase", "future_prediction", "ai_hack", "mind_blown"],
        "top_tags": [
            "#ai", "#artificialintelligence", "#tech", "#software", "#coding", "#futuretech",
            "#chatgpt", "#automation", "#shorts", "#viral"
        ],
        "title_formulas": [
            "This New AI Tool Changes {Topic} Forever",
            "How AI Is Automating {Topic} In 2026",
            "Top 3 AI Hacks For {Topic}",
            "Why {Topic} Is Replaced By AI"
        ],
        "engagement_triggers": ["mind_blown", "tool_demo", "future_insight", "efficiency_boost"]
    },
    "twists_revealed": {
        "niche": "Twists Revealed & Mind-Blowing Plot Revelations",
        "target_wpm": (145, 185),
        "ideal_duration": (20.0, 50.0),
        "hook_types": ["shocking_reveal", "plot_twist", "unspoken_truth", "ending_explained"],
        "top_tags": [
            "#twistsrevealed", "#plottwist", "#mindblown", "#shocking", "#endingexplained",
            "#unspokentruth", "#darksecrets", "#shorts", "#viral", "#fyp"
        ],
        "title_formulas": [
            "The Shocking Plot Twist In {Topic} Nobody Saw Coming",
            "What Happened At The End Of {Topic} Revealed",
            "The Dark Secret Behind {Topic} Finally Exposed",
            "Wait For The Plot Twist In {Topic}..."
        ],
        "engagement_triggers": ["curiosity_gap", "shock_value", "revelation", "ending_twist"]
    },
    "reverse_psychology_warning": {
        "niche": "Reverse Psychology & Warning Hooks (Don't Watch This)",
        "target_wpm": (150, 190),
        "ideal_duration": (15.0, 45.0),
        "hook_types": ["reverse_psychology", "warning_gate", "prohibited_knowledge", "stop_scrolling"],
        "top_tags": [
            "#dontwatchthis", "#warning", "#secret", "#forbidden", "#stopscrolling",
            "#mustsee", "#mystery", "#shorts", "#viral", "#fyp"
        ],
        "title_formulas": [
            "DO NOT Watch This If You Want To Remain {Topic}",
            "Stop Watching Right Now If You Can't Handle {Topic}",
            "Warning: This Secret About {Topic} Will Ruin Everything",
            "You Were Never Meant To See This About {Topic}"
        ],
        "engagement_triggers": ["fear_of_missing_out", "forbidden_curiosity", "warning_trigger", "high_retention"]
    },
    "cute_dosage": {
        "niche": "Cute Dosage, Wholesome & Heartwarming Clips",
        "target_wpm": (110, 150),
        "ideal_duration": (15.0, 40.0),
        "hook_types": ["wholesome_moment", "cute_animal", "heartwarming", "daily_dopamine"],
        "top_tags": [
            "#cutedosage", "#cute", "#wholesome", "#animals", "#pets", "#heartwarming",
            "#dailybooster", "#aww", "#shorts", "#viral"
        ],
        "title_formulas": [
            "Your Daily Dose Of Cute: {Topic}",
            "This Wholesome Moment Will Make Your Entire Day",
            "The Cutest {Topic} You Will See Today",
            "Try Not To Smile At This {Topic} Challenge"
        ],
        "engagement_triggers": ["dopamine_hit", "emotional_warmth", "shareability", "feel_good"]
    }
}


class ViralComparisonService:
    def __init__(self):
        self.ai = AIService()

    def get_benchmark_profile(self, niche: str = "general_viral") -> dict:
        """Fetch benchmark profile based on niche string."""
        clean_niche = niche.lower().replace(" ", "_")
        for key in BENCHMARK_PROFILES:
            if key in clean_niche or clean_niche in key:
                return BENCHMARK_PROFILES[key]
        return BENCHMARK_PROFILES["general_viral"]

    def compare_clip_to_viral(
        self,
        transcript_text: str,
        hook_text: str | None = None,
        current_tags: list[str] | None = None,
        duration_seconds: float = 30.0,
        niche: str = "general_viral",
    ) -> dict[str, Any]:
        """
        Compare clip content and tags against top viral video benchmarks across 4 axes.
        Returns detailed report + scores.
        """
        profile = self.get_benchmark_profile(niche)
        current_tags = current_tags or []
        hook_text = hook_text or (transcript_text[:120] if transcript_text else "")

        # 1. Pacing Analysis
        words = transcript_text.split() if transcript_text else []
        word_count = len(words)
        minutes = max(duration_seconds / 60.0, 0.1)
        wpm = round(word_count / minutes, 1)

        min_wpm, max_wpm = profile["target_wpm"]
        if min_wpm <= wpm <= max_wpm:
            pacing_score = 95.0
            pacing_status = "Optimal speech velocity matching top viral videos."
        elif wpm < min_wpm:
            pacing_score = max(50.0, 95.0 - (min_wpm - wpm) * 0.8)
            pacing_status = f"Pacing is slow ({wpm:.0f} WPM vs viral target {min_wpm}-{max_wpm} WPM). Increase cut frequency."
        else:
            pacing_score = max(60.0, 95.0 - (wpm - max_wpm) * 0.5)
            pacing_status = f"Pacing is fast ({wpm:.0f} WPM vs viral target {min_wpm}-{max_wpm} WPM). Trim filler words."

        # Duration score
        dur_min, dur_max = profile["ideal_duration"]
        if dur_min <= duration_seconds <= dur_max:
            duration_score = 100.0
        else:
            duration_score = 75.0

        pacing_total_score = round(pacing_score * 0.7 + duration_score * 0.3, 1)

        # 2. Tag & SEO Keyword Coverage
        target_tags = set(tag.lower() for tag in profile["top_tags"])
        existing_tags = set(tag.lower() for tag in current_tags)

        # Check tag overlap
        matched_tags = target_tags.intersection(existing_tags)
        missing_viral_tags = list(target_tags - existing_tags)

        tag_coverage = len(matched_tags) / max(len(target_tags), 1)
        tag_score = round(min(100.0, max(40.0, tag_coverage * 100.0 + len(current_tags) * 5)), 1)

        # 3. AI-Driven Hook & Content Analysis
        ai_eval = self._evaluate_hook_and_content_with_ai(
            transcript_text=transcript_text,
            hook_text=hook_text,
            profile=profile
        )

        hook_score = ai_eval.get("hook_score", 75.0)
        content_score = ai_eval.get("content_score", 78.0)
        hook_type_detected = ai_eval.get("hook_type", "general")
        gaps = ai_eval.get("gaps", [])

        # 4. Overall Viral Score & Tier Calculation
        # Weighted score: 35% Hook + 30% Content + 20% Tags + 15% Pacing
        overall_viral_score = round(
            (hook_score * 0.35) +
            (content_score * 0.30) +
            (tag_score * 0.20) +
            (pacing_total_score * 0.15),
            1
        )

        if overall_viral_score >= 90.0:
            tier = "Tier A+"
        elif overall_viral_score >= 80.0:
            tier = "Tier A"
        elif overall_viral_score >= 65.0:
            tier = "Tier B"
        else:
            tier = "Tier C"

        if missing_viral_tags:
            gaps.append(f"Missing high-performing viral tags: {', '.join(missing_viral_tags[:4])}")
        if wpm < min_wpm:
            gaps.append("Speech rate is below viral benchmark threshold. Recommend 1.1x speed boost or silence trim.")

        return {
            "niche": profile["niche"],
            "overall_viral_score": overall_viral_score,
            "tier": tier,
            "metrics": {
                "hook_score": hook_score,
                "content_score": content_score,
                "tag_score": tag_score,
                "pacing_score": pacing_total_score,
                "wpm": wpm,
                "target_wpm": profile["target_wpm"],
                "duration_seconds": duration_seconds,
            },
            "hook_analysis": {
                "detected_type": hook_type_detected,
                "status": ai_eval.get("hook_feedback", "Hook provides adequate entry point."),
            },
            "pacing_analysis": pacing_status,
            "tag_analysis": {
                "current_tags_count": len(current_tags),
                "matched_viral_tags": list(matched_tags),
                "missing_viral_tags": missing_viral_tags[:8],
            },
            "gap_analysis": gaps,
            "benchmark_targets": {
                "ideal_duration": profile["ideal_duration"],
                "target_wpm": profile["target_wpm"],
                "recommended_tags": profile["top_tags"],
            }
        }

    def generate_viral_enhancements(
        self,
        transcript_text: str,
        hook_text: str | None = None,
        current_tags: list[str] | None = None,
        niche: str = "general_viral",
    ) -> dict[str, Any]:
        """
        Generate benchmark-driven enhancements for clip content, viral tags, hooks, and titles.
        """
        profile = self.get_benchmark_profile(niche)
        current_tags = current_tags or []
        hook_text = hook_text or (transcript_text[:120] if transcript_text else "")

        # 1. Generate Enhanced Tag & Hashtag Suite
        niche_tags = profile["top_tags"]
        # Extract keywords from transcript
        words = [w.strip(".,!?\"'").lower() for w in transcript_text.split() if len(w) > 4]
        from collections import Counter
        common_words = [w for w, _ in Counter(words).most_common(6)]
        content_tags = [f"#{w}" for w in common_words]

        combined_tags = list(dict.fromkeys(niche_tags + content_tags + current_tags))[:15]
        hashtags_str = " ".join([t if t.startswith("#") else f"#{t.replace(' ', '')}" for t in combined_tags[:10]])

        # 2. AI Prompt for Rewritten Viral Hooks & Multi-Platform Metadata
        ai_metadata = self._generate_viral_metadata_with_ai(
            transcript_text=transcript_text,
            hook_text=hook_text,
            profile=profile,
            hashtags_str=hashtags_str
        )

        # 3. Recommended Editing Directives
        editing_directives = [
            "burned_in_animated_captions",
            "dynamic_zoom_cuts_every_4s",
            "audio_loudness_normalization_norm_14lufs",
            "silence_trimming_threshold_300ms",
            "sharpen_filter_luma_strength_1_2"
        ]

        return {
            "enhanced_viral_hooks": ai_metadata.get("viral_hooks", [
                f"Wait until you hear this about {profile['niche']}...",
                f"The real reason nobody talks about this...",
                f"Did you know this about {profile['niche']}?"
            ]),
            "enhanced_tags": combined_tags,
            "hashtags_string": hashtags_str,
            "platform_metadata": {
                "youtube_shorts": {
                    "title": ai_metadata.get("youtube_title", f"The Secret of {profile['niche']} #shorts"),
                    "description": f"{ai_metadata.get('description', '')}\n\n{hashtags_str}",
                    "tags": combined_tags,
                    "pinned_comment": "Subscribe for more daily clips! What do you think?"
                },
                "tiktok": {
                    "caption": f"{ai_metadata.get('tiktok_caption', '')} {hashtags_str}",
                    "sound_recommendation": "Trending High-Energy Beat / Speech Audio",
                    "hashtags": hashtags_str.split()
                },
                "instagram_reels": {
                    "caption": f"{ai_metadata.get('reels_caption', '')}\n.\n.\n{hashtags_str}",
                    "hashtags": hashtags_str.split()
                },
                "x_twitter": {
                    "post": f"{ai_metadata.get('x_post', '')}\n\n{hashtags_str[:100]}"
                }
            },
            "editing_directives": editing_directives,
        }

    def _evaluate_hook_and_content_with_ai(
        self, transcript_text: str, hook_text: str, profile: dict
    ) -> dict:
        """Use AIService to evaluate hook quality and content arc against viral standards."""
        prompt = (
            f"Target Content Niche: {profile['niche']}\n"
            f"Clip Opening Hook Text: \"{hook_text}\"\n"
            f"Full Clip Transcript: \"{transcript_text[:1500]}\"\n\n"
            "Evaluate this short video clip against top viral video standards (OpusClip/TikTok/YouTube Shorts standards).\n"
            "Provide output strictly as JSON with keys:\n"
            "- hook_score: float (0-100)\n"
            "- content_score: float (0-100)\n"
            "- hook_type: string (e.g., question, bold_claim, pattern_interrupt, story, revelation)\n"
            "- hook_feedback: string (brief explanation of hook strength)\n"
            "- gaps: list of strings (1-3 actionable gap points)"
        )
        schema = {
            "type": "object",
            "properties": {
                "hook_score": {"type": "number"},
                "content_score": {"type": "number"},
                "hook_type": {"type": "string"},
                "hook_feedback": {"type": "string"},
                "gaps": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["hook_score", "content_score", "hook_type", "hook_feedback", "gaps"]
        }

        try:
            res = self.ai.complete_json(prompt, schema=schema)
            if res:
                return res
        except Exception as exc:
            logger.warning(f"AI viral evaluation failed ({exc}); using fallback heuristics")

        # Fallback heuristic score
        is_question = "?" in hook_text
        has_numbers = bool(re.search(r'\d+', hook_text))
        h_score = 75.0 + (10.0 if is_question else 0) + (10.0 if has_numbers else 0)

        return {
            "hook_score": min(h_score, 95.0),
            "content_score": 80.0,
            "hook_type": "question" if is_question else "bold_claim",
            "hook_feedback": "Opening presents clear focus, enhance with stronger pattern interrupt.",
            "gaps": ["Add strong visual pattern interrupt in first 2 seconds."]
        }

    def _generate_viral_metadata_with_ai(
        self, transcript_text: str, hook_text: str, profile: dict, hashtags_str: str
    ) -> dict:
        """Use AIService to generate optimized viral hooks, titles, and platform captions."""
        prompt = (
            f"Niche: {profile['niche']}\n"
            f"Transcript: \"{transcript_text[:1200]}\"\n\n"
            "Generate viral short-form video metadata:\n"
            "1. viral_hooks: 3 high-converting hook opening lines (question, pattern interrupt, high curiosity)\n"
            "2. youtube_title: 1 viral YouTube Shorts title (<60 chars, high CTR formula)\n"
            "3. tiktok_caption: 1 engaging TikTok caption with CTA (<150 chars)\n"
            "4. reels_caption: 1 Instagram Reels caption\n"
            "5. x_post: 1 punchy X/Twitter post\n"
            "6. description: 1 concise description summarizing the key insight"
        )
        schema = {
            "type": "object",
            "properties": {
                "viral_hooks": {"type": "array", "items": {"type": "string"}},
                "youtube_title": {"type": "string"},
                "tiktok_caption": {"type": "string"},
                "reels_caption": {"type": "string"},
                "x_post": {"type": "string"},
                "description": {"type": "string"}
            },
            "required": ["viral_hooks", "youtube_title", "tiktok_caption", "reels_caption", "x_post", "description"]
        }

        try:
            res = self.ai.complete_json(prompt, schema=schema)
            if res:
                return res
        except Exception as exc:
            logger.warning(f"AI viral metadata generation failed ({exc}); using fallback")

        first_sentence = transcript_text.split(".")[0] if transcript_text else "Check this out"
        return {
            "viral_hooks": [
                f"You won't believe what happens when {first_sentence[:40]}...",
                f"Stop scrolling: Here's the truth about this...",
                f"The 1 secret about this you need to hear..."
            ],
            "youtube_title": f"The Unspoken Truth About This #shorts",
            "tiktok_caption": f"Watch till the end! What do you think about this? 🤔",
            "reels_caption": f"Save this for later! Share your thoughts in the comments below 👇",
            "x_post": f"Important insight you shouldn't miss.",
            "description": f"Key breakdown and viral moment from {profile['niche']}."
        }
