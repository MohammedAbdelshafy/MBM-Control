import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

from .models.source import NormalizedSource

class MomentConfidence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

class DiscoveryMethod(Enum):
    AI_PROVIDER = "AI_PROVIDER"
    RULE_FALLBACK = "RULE_FALLBACK"

@dataclass
class CandidateMoment:
    moment_id: str
    source_id: str
    
    start_seconds: int
    end_seconds: int
    duration_seconds: int
    
    moment_type: str
    
    hook_score: float # 0.0 - 1.0
    payoff_score: float # 0.0 - 1.0
    standalone_score: float # 0.0 - 1.0
    context_score: float # 0.0 - 1.0
    relevance_score: float # 0.0 - 1.0
    
    confidence: MomentConfidence
    evidence: str
    discovery_method: DiscoveryMethod
    
    total_score: float = field(init=False)
    
    def __post_init__(self):
        if self.start_seconds < 0 or self.end_seconds < 0:
            raise ValueError("Timestamps cannot be negative")
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be strictly greater than start_seconds")
        if self.duration_seconds != (self.end_seconds - self.start_seconds):
            raise ValueError("duration_seconds must equal end_seconds - start_seconds")
            
        # Deterministic ranking score calculation
        # Weights: Hook 30%, Payoff 20%, Standalone 20%, Context 10%, Relevance 20%
        self.total_score = round(
            self.hook_score * 0.30 +
            self.payoff_score * 0.20 +
            self.standalone_score * 0.20 +
            self.context_score * 0.10 +
            self.relevance_score * 0.20,
            4
        )
        
        # Penalize total score slightly if confidence is not HIGH
        if self.confidence == MomentConfidence.MEDIUM:
            self.total_score = round(self.total_score * 0.8, 4)
        elif self.confidence in (MomentConfidence.LOW, MomentConfidence.UNKNOWN):
            self.total_score = round(self.total_score * 0.5, 4)

def generate_moment_id(source_id: str, start: int, end: int) -> str:
    # Deterministic ID based on source and boundaries
    raw = f"{source_id}_{start}_{end}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()[:12]

def discover_moments(
    source: NormalizedSource, 
    transcript: Optional[str] = None, 
    ai_available: bool = True
) -> List[CandidateMoment]:
    """
    Discovers candidate moments from a source.
    """
    candidates = []
    
    # We never invent transcripts. If it's empty, we must rely on timestamps alone
    # or fail gracefully/use fallback rules.
    has_transcript = transcript is not None and len(transcript.strip()) > 0
    
    if ai_available and has_transcript:
        # Mocking an AI discovery output for the sake of the domain logic.
        # In a real implementation, this would call the LLM provider.
        c1 = CandidateMoment(
            moment_id=generate_moment_id(source.source_id, 10, 40),
            source_id=source.source_id,
            start_seconds=10,
            end_seconds=40,
            duration_seconds=30,
            moment_type="educational_hook",
            hook_score=0.9,
            payoff_score=0.8,
            standalone_score=0.85,
            context_score=0.7,
            relevance_score=0.9,
            confidence=MomentConfidence.HIGH,
            evidence="Explicit hook in transcript: 'The secret to...'",
            discovery_method=DiscoveryMethod.AI_PROVIDER
        )
        candidates.append(c1)
        
    elif not ai_available or not has_transcript:
        # Rule-based fallback
        # If we have duration, we might just clip the first 60 seconds as a 'cold open'
        dur = source.duration_seconds
        if dur and dur >= 60:
            c_fallback = CandidateMoment(
                moment_id=generate_moment_id(source.source_id, 0, 60),
                source_id=source.source_id,
                start_seconds=0,
                end_seconds=60,
                duration_seconds=60,
                moment_type="cold_open_fallback",
                hook_score=0.6,
                payoff_score=0.6,
                standalone_score=0.7,
                context_score=0.5,
                relevance_score=0.6,
                confidence=MomentConfidence.MEDIUM if has_transcript else MomentConfidence.LOW,
                evidence="Fallback rule: first 60 seconds",
                discovery_method=DiscoveryMethod.RULE_FALLBACK
            )
            candidates.append(c_fallback)
        elif dur and dur < 60:
            # The whole video is the moment
            c_fallback = CandidateMoment(
                moment_id=generate_moment_id(source.source_id, 0, dur),
                source_id=source.source_id,
                start_seconds=0,
                end_seconds=dur,
                duration_seconds=dur,
                moment_type="full_video_fallback",
                hook_score=0.6,
                payoff_score=0.6,
                standalone_score=0.7,
                context_score=0.5,
                relevance_score=0.6,
                confidence=MomentConfidence.LOW,
                evidence="Fallback rule: entire short video",
                discovery_method=DiscoveryMethod.RULE_FALLBACK
            )
            candidates.append(c_fallback)
            
    # Filter and deduplicate
    final_candidates = []
    seen_ids = set()
    
    for c in candidates:
        # Suppress completely unviable low-confidence/low-score moments
        # e.g., if total score drops below 0.3 due to penalties
        if c.total_score < 0.3:
            continue
            
        if c.moment_id not in seen_ids:
            final_candidates.append(c)
            seen_ids.add(c.moment_id)
            
    # Sort deterministically (highest score first, then by start time, then ID to break ties)
    final_candidates.sort(key=lambda x: (-x.total_score, x.start_seconds, x.moment_id))
    
    return final_candidates
