"""
MBM LeadEngine — Groq LPU Fast Classifier & Batch Inference Engine
Provides sub-500ms lead classification, rapid signal extraction, objection handling,
and bilingual (Arabic + English) classification with deterministic fallbacks.
"""

from __future__ import annotations
import os
import json
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class GroqFastClassifier:
    """Ultra-fast LPU inference engine for classification and high-throughput normalization."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GROQ_API_KEY
        self.client = None
        if self.api_key and not self.api_key.startswith("gsk_demo"):
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
            except Exception as e:
                self.client = None

    def classify_seller_intent(self, text_or_signals: str | List[str]) -> Dict[str, Any]:
        """Classifies seller motivation into HIGH, MEDIUM, LOW, or UNKNOWN with confidence."""
        if isinstance(text_or_signals, list):
            signals_str = ", ".join(text_or_signals)
        else:
            signals_str = str(text_or_signals)

        if not signals_str.strip():
            return {
                "intent": "UNKNOWN",
                "confidence": 0.0,
                "model": "rule_engine_empty",
                "latency_ms": 0.1,
                "signals": []
            }

        start_t = time.perf_counter()

        prompt = f"""
Analyze the following verified property/seller signals and classify motivation strictly into:
HIGH (urgent distress, upcoming auction, tax delinquent + vacant)
MEDIUM (absentee owner, long-term held, tired landlord)
LOW (recent buyer, strong market equity, no distress signals)
UNKNOWN (insufficient factual data)

Signals: "{signals_str}"

Respond in JSON format only:
{{"intent": "HIGH|MEDIUM|LOW|UNKNOWN", "confidence": 0.0-1.0, "reasoning": "brief factual rationale"}}
"""
        if self.client:
            try:
                chat = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are a factual real estate distress classification engine. Never invent unstated facts."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=150
                )
                latency = round((time.perf_counter() - start_t) * 1000, 2)
                res = json.loads(chat.choices[0].message.content)
                return {
                    "intent": res.get("intent", "UNKNOWN").upper(),
                    "confidence": float(res.get("confidence", 0.8)),
                    "reasoning": res.get("reasoning", ""),
                    "model": "groq/llama-3.3-70b-versatile",
                    "latency_ms": latency
                }
            except Exception as err:
                pass

        # Deterministic rule-based fallback
        latency = round((time.perf_counter() - start_t) * 1000, 2)
        sig_lower = signals_str.lower()
        if "auction" in sig_lower or ("tax" in sig_lower and "vacant" in sig_lower):
            intent = "HIGH"
            conf = 0.90
        elif "absentee" in sig_lower or "delinquent" in sig_lower or "vacant" in sig_lower:
            intent = "MEDIUM"
            conf = 0.75
        elif "owner occupied" in sig_lower or "recent" in sig_lower:
            intent = "LOW"
            conf = 0.60
        else:
            intent = "UNKNOWN"
            conf = 0.50

        return {
            "intent": intent,
            "confidence": conf,
            "reasoning": f"Deterministic signal heuristic matched from: {signals_str[:60]}",
            "model": "deterministic_rule_engine",
            "latency_ms": latency
        }

    def classify_objection(self, objection: str, lang: str = "auto") -> Dict[str, Any]:
        """Classifies cold-call objections (English + Arabic) and returns objection type."""
        start_t = time.perf_counter()
        obj_lower = objection.lower()

        # Detect Arabic vs English
        is_arabic = any('\u0600' <= c <= '\u06FF' for c in objection)
        detected_lang = "ar" if is_arabic else "en"

        if self.client:
            try:
                system_msg = "You are a cold-calling tele-sales objection classifier. Output JSON only."
                user_msg = f"""
Classify this objection: "{objection}"
Category must be one of: NOT_INTERESTED, PRICE_TOO_LOW, SEND_EMAIL, WHO_ARE_YOU, CALL_BACK_LATER, DO_NOT_CALL, GENERAL_OBJECTION.
JSON format: {{"category": "CATEGORY", "confidence": 0.0-1.0, "is_dnc": true/false}}
"""
                chat = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=100
                )
                latency = round((time.perf_counter() - start_t) * 1000, 2)
                res = json.loads(chat.choices[0].message.content)
                res["model"] = "groq/llama-3.3-70b-versatile"
                res["latency_ms"] = latency
                res["detected_lang"] = detected_lang
                return res
            except Exception:
                pass

        # Deterministic fallback
        latency = round((time.perf_counter() - start_t) * 1000, 2)
        if "remove" in obj_lower or "stop" in obj_lower or "dnc" in obj_lower or "do not call" in obj_lower or "لا تتصل" in objection:
            cat = "DO_NOT_CALL"
            is_dnc = True
        elif "not interested" in obj_lower or "مش مهتم" in objection or "غير مهتم" in objection:
            cat = "NOT_INTERESTED"
            is_dnc = False
        elif "price" in obj_lower or "how much" in obj_lower or "offer" in obj_lower or "السعر" in objection or "كم" in objection:
            cat = "PRICE_TOO_LOW"
            is_dnc = False
        elif "email" in obj_lower or "mail" in obj_lower or "ايميل" in objection or "بريد" in objection:
            cat = "SEND_EMAIL"
            is_dnc = False
        elif "who" in obj_lower or "مين" in objection or "من انت" in objection:
            cat = "WHO_ARE_YOU"
            is_dnc = False
        else:
            cat = "GENERAL_OBJECTION"
            is_dnc = False

        return {
            "category": cat,
            "confidence": 0.85,
            "is_dnc": is_dnc,
            "model": "deterministic_rule_engine",
            "latency_ms": latency,
            "detected_lang": detected_lang
        }
