"""
Content Prompt Router - AI Content Intelligence Engine
Automatically selects optimal prompts based on content generation requirements.

This module implements intelligent prompt selection using:
- Content analysis of input parameters
- Audience targeting and platform optimization
- Theme matching and tone consistency
- Context-aware routing algorithms
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import os
from pathlib import Path
@dataclass
class ContentInputs:
    """Input parameters for content generation."""
    niche: str
    audience: str
    goal: str
    platform: str
    tone: str
    offer: str
    content_type: str = "short_form"
    duration: str = "15s"
    complexity: str = "intermediate"
@dataclass
class PromptSelection:
    """Selected prompt configuration."""
    template_id: str
    workflow_type: str
    context_weights: Dict[str, float]
    platform_specific: bool
    evaluation_criteria: List[str]
class ContentPromptRouter:
    """
    Intelligent prompt router for content generation.
    
    Routes content requests to optimal prompt workflows based on:
    - Content niche and target audience
    - Platform-specific requirements
    - Conversion goals and tone preferences
    - Content format and complexity needs
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.prompt_templates = self._load_prompt_templates()
        self.workflows = self._define_workflows()
        self.platform_optimizations = self._define_platform_optimizations()
        self.niche_routing = self._define_niche_routing()
        self.audience_segments = self._define_audience_segments()

    def _get_default_config_path(self) -> str:
        """Get default configuration file path."""
        base_dir = Path(__file__).parent.parent
        return str(base_dir / "content-engine" / "config" / "prompt_routing.json")

    def _load_prompt_templates(self) -> Dict[str, Any]:
        """Load prompt templates configuration."""
        template_path = Path(__file__).parent / "templates" / "prompt_templates.json"
        if template_path.exists():
            with open(template_path, 'r') as f:
                return json.load(f)
        else:
            return self._get_default_templates()

    def _get_default_templates(self) -> Dict[str, Any]:
        """Get default prompt templates."""
        return {
            "construction": {
                "lead_generation": "Generate high-converting real estate lead content",
                "brand_awareness": "Build credibility in construction industry",
                "service_promotion": "Promote construction services effectively"
            },
            "ai_technology": {
                "lead_generation": "Capture AI solution prospects",
                "thought_leadership": "Establish AI expertise",
                "product_promotion": "Market AI products"
            },
            "real_estate": {
                "lead_generation": "Generate property investment content",
                "property_management": "Create rental property content",
                "market_analysis": "Analyze real estate trends"
            },
            "general": {
                "lead_generation": "Generic lead generation content",
                "education": "Educational content for lead nurturing",
                "entertainment": "Entertaining content for engagement"
            }
        }

    def _define_workflows(self) -> Dict[str, Any]:
        """Define content generation workflows."""
        return {
            "trend_analysis": {
                "name": "Trend Analysis",
                "description": "Analyze viral trends and audience behavior patterns",
                "estimated_time": "5-10 seconds",
                "platforms": ["TikTok", "YouTube Shorts", "Instagram", "X"],
                "output_format": "insights"
            },
            "hook_generation": {
                "name": "Hook Generation",
                "description": "Create attention-grabbing opening hooks optimized for platform",
                "estimated_time": "10-15 seconds",
                "platforms": ["TikTok", "YouTube Shorts", "Instagram"],
                "output_format": "script_segment"
            },
            "audience_analysis": {
                "name": "Audience Analysis",
                "description": "Deep dive into target audience demographics and preferences",
                "estimated_time": "5-10 seconds",
                "platforms": ["All platforms"],
                "output_format": "audience_profile"
            },
            "story_structure": {
                "name": "Story Structure",
                "description": "Build complete narrative arc with engagement points",
                "estimated_time": "15-30 seconds",
                "platforms": ["YouTube Shorts", "Instagram"],
                "output_format": "script_structured"
            },
            "dialogue_generation": {
                "name": "Dialogue Generation",
                "description": "Generate natural conversational content",
                "estimated_time": "10-15 seconds",
                "platforms": ["TikTok", "Instagram"],
                "output_format": "dialogue_script"
            },
            "credibility_building": {
                "name": "Credibility Building",
                "description": "Establish authority and trust through social proof",
                "estimated_time": "5-10 seconds",
                "platforms": ["All platforms"],
                "output_format": "proof_elements"
            },
            "testimony_collection": {
                "name": "Testimony Collection",
                "description": "Gather authentic user testimonials and case studies",
                "estimated_time": "10-15 seconds",
                "platforms": ["All platforms"],
                "output_format": "testimony_content"
            },
            "metrics_validation": {
                "name": "Metrics Validation",
                "description": "Validate content against performance benchmarks",
                "estimated_time": "5-10 seconds",
                "platforms": ["All platforms"],
                "output_format": "validation_report"
            },
            "content_optimization": {
                "name": "Content Optimization",
                "description": "Optimize content for platform algorithms and user engagement",
                "estimated_time": "10-15 seconds",
                "platforms": ["All platforms"],
                "output_format": "optimized_content"
            },
            "call_to_action_optimization": {
                "name": "Call-to-Action Optimization",
                "description": "Craft compelling calls-to-action for conversion",
                "estimated_time": "5-10 seconds",
                "platforms": ["All platforms"],
                "output_format": "cta_elements"
            },
            "multi_platform_adaptation": {
                "name": "Multi-Platform Adaptation",
                "description": "Adapt content for different platform requirements",
                "estimated_time": "10-15 seconds",
                "platforms": ["TikTok", "YouTube Shorts", "Instagram", "X"],
                "output_format": "adapted_content"
            },
            "validation": {
                "name": "Content Validation",
                "description": "Validate content quality and effectiveness",
                "estimated_time": "5-10 seconds",
                "platforms": ["All platforms"],
                "output_format": "validation_score"
            },
            "optimization": {
                "name": "Content Optimization",
                "description": "Optimize content based on performance data",
                "estimated_time": "5-10 seconds",
                "platforms": ["All platforms"],
                "output_format": "optimized_content"
            }
        }

    def _define_platform_optimizations(self) -> Dict[str, Any]:
        """Define platform-specific optimizations."""
        return {
            "TikTok": {
                "optimal_hook_length": "1-3 seconds",
                "format_preferences": ["vertical_video", "text_overlay", "quick_cuts"],
                "trending_keywords": ["viral", "trending", "2024"],
                "emoji_usage": "high",
                "call_to_action_style": "direct_and_clear"
            },
            "YouTube Shorts": {
                "optimal_hook_length": "3-7 seconds",
                "format_preferences": ["caption_heavy", "visual_storytelling", "dynamic_editing"],
                "title_requirements": ["clear_value_prop", "keywords_included"],
                "call_to_action_style": "educational_and_nurturing"
            },
            "Instagram": {
                "optimal_hook_length": "2-5 seconds",
                "format_preferences": ["carousel", "reels", "stories"],
                "aesthetic_requirements": ["cohesive_branding", "high_quality_visuals"],
                "call_to_action_style": "community_building"
            },
            "X (Twitter)": {
                "optimal_hook_length": "1-2 seconds",
                "format_preferences": ["text_first", "thread_ready", "quoteable_insights"],
                "engagement_style": "conversational_and_direct",
                "call_to_action_style": "click_through_and_sharing"
            }
        }

    def _define_niche_routing(self) -> Dict[str, Any]:
        """Define niche-specific routing rules."""
        return {
            "construction": {
                "primary_workflow": "viral_hook_pipeline",
                "secondary_workflows": ["script_generation_pipeline"],
                "target_audiences": ["homeowners", "contractors", "investors"],
                "content_themes": ["new_homes", "remodels", "investment_returns"],
                "urgency_levels": ["time_sensitive", "budget_sensitive", "seasonal"]
            },
            "ai_technology": {
                "primary_workflow": "complete_campaign_pipeline",
                "secondary_workflows": ["social_proof_pipeline"],
                "target_audiences": ["tech_enthusiasts", "business_leaders", "developers"],
                "content_themes": ["ai_tools", "automation", "productivity"],
                "urgency_levels": ["urgency_driven", "scarcity_based", "expert_authority"]
            },
            "real_estate": {
                "primary_workflow": "viral_hook_pipeline",
                "secondary_workflows": ["social_proof_pipeline"],
                "target_audiences": [" homebuyers", "sellers", "investors"],
                "content_themes": ["property_values", "market_trends", "investment_opportunities"],
                "urgency_levels": ["deadline_driven", "market_timing", "competition_based"]
            },
            "lead_generation": {
                "primary_workflow": "complete_campaign_pipeline",
                "secondary_workflows": ["social_proof_pipeline"],
                "target_audiences": ["prospects", "customers", "clients"],
                "content_themes": ["service_benefits", "case_studies", "testimonials"],
                "urgency_levels": ["action_urgency", "roi_driven", "results_based"]
            }
        }

    def _define_audience_segments(self) -> Dict[str, Any]:
        """Define audience segment targeting."""
        return {
            "homeowners": {
                "voice_tone": "approachable_and_experienced",
                "language_complexity": "intermediate",
                "emotion_triggers": ["security", "investment_return", "peace_of_mind"],
                "visual_preferences": ["clean_and_organized", "professional", "trustworthy"]
            },
            "tech_enthusiasts": {
                "voice_tone": "innovative_and_forward_looking",
                "language_complexity": "advanced",
                "emotion_triggers": ["curiosity", "efficiency", "competitive_advantage"],
                "visual_preferences": ["dynamic_and_fast_paced", "modern", "tech_forward"]
            },
            "business_leaders": {
                "voice_tone": "authoritative_and_results_focused",
                "language_complexity": "expert_level",
                "emotion_triggers": ["roi", "profitability", "strategic_value"],
                "visual_preferences": ["professional_and_clean", "data_driven", "mininal_visuals"]
            },
            "young_professionals": {
                "voice_tone": "relatable_and_insightful",
                "language_complexity": "conversational",
                "emotion_triggers": ["aspiration", "growth", "community"],
                "visual_preferences": ["lively_and_vibrant", "authentic", "action_oriented"]
            }
        }

    def route_content(self, inputs: ContentInputs) -> PromptSelection:
        """
        Route content request to optimal prompt workflow.
        
        Args:
            inputs: Content generation parameters
            
        Returns:
            PromptSelection: Optimal workflow configuration
        """
        # Analyze niche for primary routing
        niche_routing = self.niche_routing.get(inputs.niche, self.niche_routing["general"])
        
        # Determine audience segment for fine-tuning
        audience_segment = self._get_closest_audience(inputs.audience)
        
        # Evaluate workflow options based on goal and platform
        workflow_scores = self._evaluate_workflows(
            niche_routing["primary_workflow"],
            niche_routing.get("secondary_workflows", []),
            inputs.goal,
            inputs.platform,
            inputs.audience
        )
        
        # Select optimal workflow
        primary_workflow = workflow_scores["primary_workflow"]
        
        # Determine platform optimization requirements
        platform_opt = self.platform_optimizations.get(inputs.platform, {})
        
        # Define evaluation criteria based on goal and audience
        evaluation_criteria = self._define_evaluation_criteria(
            inputs.goal, inputs.platform, audience_segment
        )
        
        # Create prompt selection
        selection = PromptSelection(
            template_id=f"{inputs.niche}_{inputs.goal}",
            workflow_type=primary_workflow["type"],
            context_weights=primary_workflow["context_weights"],
            platform_specific=len(platform_opt) > 0,
            evaluation_criteria=evaluation_criteria
        )
        
        return selection

    def _get_closest_audience(self, audience: str) -> str:
        """Get closest matching audience segment."""
        for segment in self.audience_segments.keys():
            if segment in audience.lower() or audience.lower() in segment:
                return segment
        return "homeowners"  # default fallback

    def _evaluate_workflows(self, primary_workflow: str, secondary_workflows: list,
                           goal: str, platform: str, audience: str) -> Dict[str, Any]:
        """Evaluate workflows based on requirements."""
        workflow = self.workflows.get(primary_workflow, {})
        
        # Calculate workflow score based on goal match
        goal_score = self._calculate_goal_score(goal, workflow)
        
        # Calculate platform compatibility score
        platform_score = self._calculate_platform_score(platform, workflow)
        
        # Calculate audience targeting score
        audience_score = self._calculate_audience_score(audience, workflow)
        
        # Determine secondary workflow options
        secondary_options = []
        for secondary in secondary_workflows:
            secondary_workflow = self.workflows.get(secondary, {})
            secondary_score = (
                self._calculate_goal_score(goal, secondary_workflow) * 0.7 +
                self._calculate_platform_score(platform, secondary_workflow) * 0.3
            )
            if secondary_score > 60:  # Threshold for inclusion
                secondary_options.append({
                    "workflow": secondary,
                    "score": secondary_score,
                    "rationale": f"Secondary workflow for {goal} on {platform}"
                })
        
        return {
            "primary_workflow": {
                "name": primary_workflow,
                "type": workflow.get("workflow_type", "pipeline"),
                "score": (goal_score + platform_score + audience_score) / 3,
                "rationale": f"Primary workflow for {inputs.niche} {goal}",
                "context_weights": workflow.get("context_weights", {})
            },
            "secondary_workflows": secondary_options,
            "overall_recommendation": "Use primary workflow with potential secondary options"
        }

    def _calculate_goal_score(self, goal: str, workflow: Dict[str, Any]) -> float:
        """Calculate how well workflow matches goal."""
        goal_mappings = {
            "lead_generation": ["lead", "generate", "prospect", "convert"],
            "brand_awareness": ["brand", "awareness", "recognize", "visibility"],
            "service_promotion": ["service", "promote", "market", "sell"],
            "sales": ["sales", "revenue", "conversion", "profit"],
            "education": ["educate", "teach", "learn", "train"],
            "entertainment": ["entertain", "engage", "fun", " Viral"]
        }
        
        goal_lower = goal.lower()
        workflow_goals = workflow.get("goals", [goal]) if "goals" in workflow else [goal]
        
        score = 0
        for workflow_goal in workflow_goals:
            for goal_keyword in goal_mappings.get(goal, goal_mappings["lead_generation"]):
                if workflow_goal.lower() == goal_lower or \
                   goal_keyword in workflow_goal.lower() or \
                   workflow_goal.lower() in goal_lower:
                    score += 100
                    break
        
        return min(score, 100)

    def _calculate_platform_score(self, platform: str, workflow: Dict[str, Any]) -> float:
        """Calculate how well workflow supports platform."""
        platform_optimizations = self.platform_optimizations.get(platform, {})
        
        if not platform_optimizations:
            return 50  # Neutral score
        
        # Check if workflow has platform-specific adaptations
        workflow_platforms = workflow.get("platforms", [])
        if platform in workflow_platforms:
            return 100
        
        # Check if workflow is generic across platforms
        generic_platforms = workflow.get("generic_platforms", [])
        if platform in generic_platforms:
            return 75
        
        return 25

    def _calculate_audience_score(self, audience: str, workflow: Dict[str, Any]) -> float:
        """Calculate how well workflow targets the audience."""
        audience_segment = self._get_closest_audience(audience)
        audience_opt = self.audience_segments.get(audience_segment, {})
        
        if not audience_opt:
            return 50
        
        # Check for audience targeting in workflow
        workflow_audience_targets = workflow.get("audience_targets", [])
        if audience_segment in workflow_audience_targets:
            return 100
        
        # Check for generic audience targeting
        generic_audience_targets = workflow.get("generic_audience_targets", [])
        if len(generic_audience_targets) > 0:
            return 75
        
        return 25

    def _define_evaluation_criteria(self, goal: str, platform: str, audience: str) -> List[str]:
        """Define evaluation criteria based on requirements."""
        criteria = []
        
        # Goal-based criteria
        if "lead" in goal.lower():
            criteria.extend(["conversion_potential", "call_to_action_effectiveness"])
        elif "brand" in goal.lower():
            criteria.extend(["brand_alignment", "message_clarity"])
        elif "educate" in goal.lower():
            criteria.extend(["educational_value", "information_density"])
        elif "entertain" in goal.lower():
            criteria.extend(["engagement_potential", "shareability"])
        
        # Platform-based criteria
        if platform == "TikTok":
            criteria.extend(["hook_strength", "first_second_impact", "trending_potential"])
        elif platform == "YouTube Shorts":
            criteria.extend(["script_quality", "visual_storytelling", "call_to_action"])
        elif platform == "Instagram":
            criteria.extend(["aesthetic_consistency", "engagement_triggers", "save_ability"])
        elif platform == "X":
            criteria.extend(["text_clarity", "thread_readability", "shareability"])
        
        # Add universal criteria
        criteria.extend(["audience_relevance", "content_quality", "platform_fit"])
        
        return criteria

    def get_prompt_template(self, template_id: str, inputs: ContentInputs) -> Dict[str, Any]:
        """
        Get prompt template based on template ID and inputs.
        
        Args:
            template_id: Unique template identifier
            inputs: Content generation parameters
            
        Returns:
            Dict containing prompt template and context
        """
        template = self.prompt_templates.get(template_id, {})
        
        if not template:
            # Return default template
            template = self.prompt_templates.get("general_lead_generation", {})
        
        # Customize template based on inputs
        customized_template = self._customize_template(template, inputs)
        
        return {
            "template_id": template_id,
            "template": customized_template,
            "inputs": inputs,
            "platform_optimizations": self.platform_optimizations.get(inputs.platform, {}),
            "workflow": self.workflows.get(template.get("workflow", "viral_hook_pipeline"), {}),
            "generation_parameters": self._generate_template_parameters(inputs)
        }

    def _customize_template(self, template: Dict[str, Any], inputs: ContentInputs) -> str:
        """Customize prompt template based on inputs."""
        base_template = template.get("template", "")
        
        # Replace placeholders with actual values
        customizations = {
            "{{NICHE}}": inputs.niche,
            "{{AUDIENCE}}": inputs.audience,
            "{{GOAL}}": inputs.goal,
            "{{PLATFORM}}": inputs.platform,
            "{{TONE}}": inputs.tone,
            "{{OFFER}}": inputs.offer,
            "{{AUDIENCE_PREFERENCES}}": self._get_audience_customization(inputs.audience),
            "{{PLATFORM_OPTIMIZATIONS}}": self._get_platform_customization(inputs.platform),
            "{{PLATFORM_CONSTRAINTS}}": self._get_platform_constraints(inputs.platform),
            "{{AUDIENCE_BEHAVIORS}}": self._get_audience_behaviors(inputs.audience)
        }
        
        customized = base_template
        for placeholder, value in customizations.items():
            customized = customized.replace(placeholder, str(value))
        
        return customized

    def _get_audience_customization(self, audience: str) -> str:
        """Get audience-specific customization text."""
        segment = self._get_closest_audience(audience)
        audience_opt = self.audience_segments.get(segment, {})
        
        return f"""
Audience Profile:
- Demographics: {segment.replace('_', ' ').title()}
- Voice Tone: {audience_opt.get('voice_tone', 'professional')}
- Language Complexity: {audience_opt.get('language_complexity', 'intermediate')}
- Key Emotional Triggers: {', '.join(audience_opt.get('emotion_triggers', []))}
- Visual Preferences: {', '.join(audience_opt.get('visual_preferences', []))}
"""

    def _get_platform_customization(self, platform: str) -> str:
        """Get platform-specific customization text."""
        platform_opt = self.platform_optimizations.get(platform, {})
        
        return f"""
Platform Constraints:
- Optimal Hook Length: {platform_opt.get('optimal_hook_length', '3-7 seconds')}
- Format Requirements: {', '.join(platform_opt.get('format_preferences', []))}
- Optimization Focus: {', '.join(platform_opt.get('format_preferences', [])[:3])}
- Call to Action Style: {platform_opt.get('call_to_action_style', 'direct')}
"""

    def _get_platform_constraints(self, platform: str) -> str:
        """Get platform-specific constraints."""
        constraints = {
            "TikTok": "15-second maximum, high-impact opening, subtitles-friendly",
            "YouTube Shorts": "60-second maximum, narrative storytelling, caption-heavy",
            "Instagram": "Vertical format, aesthetic consistency, save-friendly",
            "X": "Text-first, concise messaging, thread-optimized"
        }
        
        return constraints.get(platform, "Standard social media format")

    def _get_audience_behaviors(self, audience: str) -> str:
        """Get audience behavior insights."""
        behaviors = {
            "homeowners": "Research-heavy, risk-averse, seek credibility, value expertise",
            "tech_enthusiasts": "Quick consumption, trend-focused, novelty-seeking, shareable",
            "business_leaders": "Results-driven, data-oriented, time-constrained, efficiency-seeking",
            "young_professionals": "Socially-connected, visual-driven, experience-seeking, community-oriented"
        }
        
        segment = self._get_closest_audience(audience)
        return behaviors.get(segment, "General audience, standard social media behavior")

    def _generate_template_parameters(self, inputs: ContentInputs) -> Dict[str, Any]:
        """Generate additional parameters for template customization."""
        return {
            "content_length": self._estimate_content_length(inputs),
            "emotional_pitch": self._determine_emotional_pitch(inputs),
            "engagement_hooks": self._generate_engagement_hooks(inputs),
            "call_to_action_strategies": self._define_communication_strategies(inputs),
            "platform_specific_rules": self._get_platform_specific_rules(inputs.platform)
        }

    def _estimate_content_length(self, inputs: ContentInputs) -> str:
        """Estimate required content length."""
        if inputs.platform == "TikTok":
            return "9-15 seconds"
        elif inputs.platform == "YouTube Shorts":
            return "45-60 seconds"
        elif inputs.platform == "Instagram":
            return "2-5 minutes (posts) or 15-60 seconds (reels)"
        elif inputs.platform == "X":
            return "280-1000 characters"
        return "unknown"

    def _determine_emotional_pitch(self, inputs: ContentInputs) -> str:
        """Determine emotional pitch based on audience and goal."""
        audience_segment = self._get_closest_audience(inputs.audience)
        audience_opt = self.audience_segments.get(audience_segment, {})
        
        emotion_triggers = audience_opt.get("emotion_triggers", [])
        return ", ".join(emotion_triggers[:2]) if emotion_triggers else "professional"

    def _generate_engagement_hooks(self, inputs: ContentInputs) -> List[str]:
        """Generate engagement hooks based on platform and audience."""
        platform_opt = self.platform_optimizations.get(inputs.platform, {})
        hooks = platform_opt.get("engagement_hooks", [])
        
        if not hooks:
            hooks = [
                "Curiosity gap hooks",
                "Pain point identification",
                "Value proposition statements",
                "Social proof elements"
            ]
        
        return hooks

    def _define_communication_strategies(self, inputs: ContentInputs) -> List[str]:
        """Define communication strategies based on goal."""
        strategies = {
            "lead_generation": [
                "Direct call to action",
                "Value proposition presentation",
                "Objection handling",
                "Scarcity and urgency"
            ],
            "brand_awareness": [
                "Storytelling",
                "Emotional connection",
                "expert positioning",
                "community building"
            ],
            "service_promotion": [
                "Benefit demonstration",
                "Social proof",
                "urgency creation",
                "comparison framing"
            ]
        }
        
        goal_strategies = strategies.get(inputs.goal, strategies["lead_generation"])
        return goal_strategies

    def _get_platform_specific_rules(self, platform: str) -> Dict[str, Any]:
        """Get platform-specific rules and constraints."""
        platform_rules = {
            "TikTok": {
                "character_limit": 280,
                "emphasis_on": ["visual_hooks", "text_overlays", "audio_elements"],
                "engagement_factors": ["challenge_eligibility", "trending_audio", "hashtag_effectiveness"],
                "algorithm_preferences": ["watch_time", "completion_rate", "shares_and_comments"]
            },
            "YouTube Shorts": {
                "minimum_duration": 15,
                "maximum_duration": 60,
                "emphasis_on": [" storytelling", "visual_production", "caption_quality"],
                "engagement_factors": ["watch_time", "subscription_rate", "likes"],
                "algorithm_preferences": ["viewer_retention", "click_through_rate", "watch_time"]
            },
            "Instagram": {
                "emphasis_on": ["aesthetic_consistency", "high_quality_visuals", "engagement_metrics"],
                "engagement_factors": ["saves", "comments", "story_interactions"],
                "algorithm_preferences": ["engagement_rate", "relationship_signals", "recency"]
            },
            "X": {
                "character_limit": 280,
                "emphasis_on": ["text_content", "thread_structure", "quoteability"],
                "engagement_factors": ["retweets", "quotes", "replies"],
                "algorithm_preferences": ["engagement_quality", "network_influence", "timeliness"]
            }
        }
        
        return platform_rules.get(platform, {})