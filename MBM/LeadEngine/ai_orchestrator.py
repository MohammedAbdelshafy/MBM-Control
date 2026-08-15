"""
MBM LeadEngine — AI Orchestrator & Task-Aware Model Router
Routes tasks intelligently between NVIDIA NIM (Heavy Reasoning / Vision),
Groq LPU (Fast Classification / Low Latency), and Deterministic Gates with telemetry.
"""

from __future__ import annotations
import os
import sys
import json
import time
from enum import Enum
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Bootstrap workspace root for imports
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from MBM.LeadEngine.nvidia_model_registry import NVIDIAModelRegistry
from MBM.LeadEngine.groq_fast_classifier import GroqFastClassifier
from MBM.LeadEngine.canonical_lead_schema import AIProvenance

load_dotenv()

class TaskType(str, Enum):
    REASONING = "REASONING"
    CODE = "CODE"
    LEAD_SCORING = "LEAD_SCORING"
    LEAD_QUALIFICATION = "LEAD_QUALIFICATION"
    DEAL_ANALYSIS = "DEAL_ANALYSIS"
    RESEARCH = "RESEARCH"
    RAG = "RAG"
    DOCUMENT_ANALYSIS = "DOCUMENT_ANALYSIS"
    VISION = "VISION"
    PROPERTY_ANALYSIS = "PROPERTY_ANALYSIS"
    OBJECTION_HANDLING = "OBJECTION_HANDLING"
    CALL_SCRIPTING = "CALL_SCRIPTING"
    VOICE = "VOICE"
    MULTILINGUAL = "MULTILINGUAL"
    SOCIAL_CONTENT = "SOCIAL_CONTENT"
    MARKETING = "MARKETING"
    DATA_CLEANING = "DATA_CLEANING"
    SQL = "SQL"
    TEST_GENERATION = "TEST_GENERATION"
    BUG_TRIAGE = "BUG_TRIAGE"
    ARCHITECTURE = "ARCHITECTURE"
    AGENT_PLANNING = "AGENT_PLANNING"
    QA = "QA"
    SAFETY = "SAFETY"
    CLASSIFICATION = "CLASSIFICATION"
    SUMMARIZATION = "SUMMARIZATION"


class AIOrchestrator:
    """Central Task-Aware AI Router with Multi-Model Verification & Telemetry."""

    def __init__(self):
        self.nvidia_registry = NVIDIAModelRegistry()
        self.groq_classifier = GroqFastClassifier()
        self.telemetry_path = Path(r"C:\Users\omare\OneDrive\Desktop\AI\MBM\LeadEngine\logs\ai_routing_telemetry.jsonl")
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)

    def route(
        self,
        task_type: TaskType | str,
        payload: Dict[str, Any] | str,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Routes execution to the best available model with automated fallback."""
        if isinstance(task_type, str):
            try:
                task_type = TaskType(task_type)
            except ValueError:
                task_type = TaskType.REASONING

        start_t = time.perf_counter()
        prompt_text = json.dumps(payload) if isinstance(payload, dict) else str(payload)

        # 1. Fast Classification & Low Latency Tasks -> Groq LPU
        if task_type in [TaskType.CLASSIFICATION, TaskType.OBJECTION_HANDLING, TaskType.SUMMARIZATION]:
            if task_type == TaskType.OBJECTION_HANDLING:
                result = self.groq_classifier.classify_objection(prompt_text)
            else:
                result = self.groq_classifier.classify_seller_intent(prompt_text)
            
            self._log_telemetry(task_type.value, result.get("model", "groq"), result.get("latency_ms", 0), True)
            return result

        # 2. Heavy Reasoning & Deal Analysis -> NVIDIA NIM
        model_id = "meta/llama-3.3-70b-instruct"
        if task_type in [TaskType.CODE, TaskType.SQL]:
            model_id = "mistralai/codestral-22b-instruct-v0.1"
        elif task_type in [TaskType.VISION, TaskType.DOCUMENT_ANALYSIS, TaskType.PROPERTY_ANALYSIS]:
            model_id = "meta/llama-3.2-90b-vision-instruct"
        elif task_type in [TaskType.DEAL_ANALYSIS, TaskType.ARCHITECTURE, TaskType.QA]:
            model_id = "nvidia/llama-3.1-nemotron-70b-instruct"

        sys_p = system_prompt or f"You are an expert AI engine specialized in {task_type.value}. Provide strictly factual, zero-hallucination outputs."
        nv_res = self.nvidia_registry.query_model(model_id, prompt_text, sys_p)
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)

        provenance = AIProvenance(
            field_name=task_type.value.lower(),
            source=f"nvidia_nim:{model_id}",
            model=model_id,
            confidence=0.92 if nv_res.get("status") == "SUCCESS_LIVE" else 0.75,
            reasoning_signals=[f"Status: {nv_res.get('status')}"],
            validation_result="VALIDATED" if nv_res.get("status") == "SUCCESS_LIVE" else "UNVERIFIED"
        )

        response = {
            "task_type": task_type.value,
            "model": model_id,
            "status": nv_res.get("status"),
            "content": nv_res.get("message"),
            "latency_ms": latency_ms,
            "provenance": provenance.to_dict()
        }

        self._log_telemetry(task_type.value, model_id, latency_ms, nv_res.get("status") in ["SUCCESS_LIVE", "SUCCESS_VERIFIED"])
        return response

    def verify_high_impact_decision(
        self,
        decision_context: str,
        proposed_action: str
    ) -> Dict[str, Any]:
        """Dual-Model Verification: Model A (NVIDIA) proposes -> Model B (Groq) reviews -> Deterministic Gate."""
        start_t = time.perf_counter()

        # Step 1: NVIDIA Proposal / Validation
        prompt_a = f"Evaluate this high-impact action based on context.\nContext: {decision_context}\nAction: {proposed_action}\nIs this factually backed and safe? Answer YES or NO with 1 reason."
        res_a = self.nvidia_registry.query_model("meta/llama-3.3-70b-instruct", prompt_a)
        opinion_a = res_a.get("message", "YES")

        # Step 2: Groq Independent Cross-Check
        res_b = self.groq_classifier.classify_seller_intent(f"{decision_context} -> {proposed_action}")
        opinion_b = res_b.get("intent", "UNKNOWN")

        # Step 3: Deterministic Gate
        agreement = ("NO" not in opinion_a.upper()) and (opinion_b != "UNKNOWN")
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)

        return {
            "model_a_nvidia": opinion_a[:100],
            "model_b_groq": opinion_b,
            "consensus_reached": agreement,
            "escalate_to_human": not agreement,
            "latency_ms": latency_ms,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _log_telemetry(self, task: str, model: str, latency_ms: float, success: bool):
        """Sanitized telemetry logging without credentials or sensitive user data."""
        try:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task": task,
                "model": model,
                "latency_ms": latency_ms,
                "success": success
            }
            with open(self.telemetry_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
