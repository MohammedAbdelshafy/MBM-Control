from __future__ import annotations
import math
from datetime import datetime, timezone
from typing import Any

from MBM.CommercialRadar.candidate import PainCandidate

class EvidenceScoring:
    """Deterministic evidence scoring engine.
    
    Features:
    - Formula versioning
    - Fixed score cap
    - Sqrt corroboration for multiple similar signals
    - 30-day recency decay
    - Ambiguity-biased collapse based on independence keys
    """
    
    FORMULA_VERSION = "v1.0"
    SCORE_CAP = 100.0
    RETENTION_DAYS = 30
    
    EVENT_WEIGHTS = {
        "signal_detected": 5.0,
        "demo_booked": 25.0,
        "payment": 50.0,
        "closed_won": 75.0,
        "refund": -SCORE_CAP,
        "churn": -SCORE_CAP,
        "hard_rejection": -20.0
    }

    @classmethod
    def score_candidate(cls, candidate: PainCandidate, current_time: datetime | None = None) -> float:
        if current_time is None:
            current_time = datetime.now(timezone.utc)
            
        # Group events by independence key (to prevent spamming the same signal)
        # Assuming events might have their own source independence in metadata,
        # but the candidate itself has a primary independence_key.
        # For this slice, we will group by event_type to apply sqrt corroboration.
        
        type_counts: dict[str, int] = {}
        total_score = 0.0
        
        for event in candidate.events:
            try:
                # Handle isoformat
                ts = event.timestamp.replace("Z", "+00:00")
                event_date = datetime.fromisoformat(ts)
                if event_date.tzinfo is None:
                    event_date = event_date.replace(tzinfo=timezone.utc)
                    
                days_old = (current_time - event_date).days
                if days_old > cls.RETENTION_DAYS:
                    continue  # 30-day retention period invariant
                
                # Recency decay (linear decay over 30 days for positive signals)
                decay_factor = max(0.1, 1.0 - (days_old / cls.RETENTION_DAYS))
                
                weight = cls.EVENT_WEIGHTS.get(event.event_type, 1.0)
                
                if weight < 0:
                    total_score += weight # negative signals don't decay and don't get sqrt capped
                else:
                    type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
                    # Sqrt corroboration: the Nth signal of the same type is worth 1/sqrt(N)
                    corroboration = 1.0 / math.sqrt(type_counts[event.event_type])
                    total_score += weight * corroboration * decay_factor
                    
            except ValueError:
                continue

        # Ambiguity-biased collapse: 
        # If candidate state is rejected, force negative score
        if candidate.state == "rejected":
            return -cls.SCORE_CAP
            
        return max(-cls.SCORE_CAP, min(cls.SCORE_CAP, total_score))
