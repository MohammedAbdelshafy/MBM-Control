"""
MBM LeadEngine — Buyer Matching Engine
=======================================
Scores the fit between a property and a buyer buy-box.
"""

from typing import List, Dict, Any
from MBM.LeadEngine.canonical_lead_schema import CanonicalBuyer, BuyerMatch

class BuyerMatchingEngine:
    def __init__(self):
        pass

    def match_property_to_buyers(self, property_data: Dict[str, Any], buyers: List[CanonicalBuyer]) -> List[BuyerMatch]:
        """
        Calculates a 0-100 match score for each buyer against the property.
        Only returns matches with score >= 50.
        """
        matches = []
        for buyer in buyers:
            match = self._calculate_match(property_data, buyer)
            if match.match_score >= 50.0:
                matches.append(match)
        
        # Sort by score descending
        matches.sort(key=lambda x: x.match_score, reverse=True)
        return matches

    def _calculate_match(self, property_data: Dict[str, Any], buyer: CanonicalBuyer) -> BuyerMatch:
        score = 0.0
        match_reasons = []
        mismatch_reasons = []

        # 1. Geographic Match - State (Required, 40 pts)
        prop_state = str(property_data.get("state", "")).upper()
        if buyer.state and prop_state != buyer.state.upper():
            mismatch_reasons.append(f"State mismatch ({prop_state} vs {buyer.state})")
            return BuyerMatch(buyer_id=buyer.buyer_id, property_id=property_data.get("id", ""), match_score=0.0, mismatch_reasons=mismatch_reasons)
        elif buyer.state:
            match_reasons.append("State match")
            score += 40.0
        else:
            match_reasons.append("State criteria open")
            score += 40.0

        # 2. Geographic Match - County (20 pts)
        prop_county = str(property_data.get("county", property_data.get("city", ""))).upper()
        if buyer.county and buyer.county.upper() in prop_county:
            match_reasons.append(f"County match ({buyer.county})")
            score += 20.0
        elif not buyer.county:
            match_reasons.append("County criteria open")
            score += 20.0
        else:
            mismatch_reasons.append("County/City mismatch")

        # 3. Acreage Match (20 pts)
        acreage = float(property_data.get("acreage", 0.0))
        if buyer.min_acres > 0 and acreage < buyer.min_acres:
            mismatch_reasons.append(f"Too small ({acreage} < {buyer.min_acres} acres)")
        elif buyer.max_acres > 0 and acreage > buyer.max_acres:
            mismatch_reasons.append(f"Too large ({acreage} > {buyer.max_acres} acres)")
        else:
            if buyer.min_acres > 0 or buyer.max_acres > 0:
                match_reasons.append(f"Acreage fits buy-box ({acreage} acres)")
            else:
                match_reasons.append("Acreage criteria open")
            score += 20.0

        # 4. Zoning Match (10 pts)
        prop_zoning = str(property_data.get("zoning", "")).upper()
        if prop_zoning and buyer.zoning:
            zoning_matched = False
            for z in buyer.zoning:
                if z.upper() in prop_zoning:
                    zoning_matched = True
                    break
            if zoning_matched:
                match_reasons.append(f"Zoning match ({prop_zoning})")
                score += 10.0
            else:
                mismatch_reasons.append(f"Zoning mismatch ({prop_zoning})")
        else:
            match_reasons.append("Zoning criteria open")
            score += 10.0

        # 5. Absentee Owner (Bonus 10 pts)
        is_absentee = property_data.get("absentee_owner", False)
        if is_absentee:
            match_reasons.append("Absentee owner")
            score += 10.0

        # Ensure score is within 0-100
        score = max(0.0, min(100.0, score))

        evidence = "; ".join(match_reasons) if score >= 50 else "; ".join(mismatch_reasons)
        confidence = 90.0 if property_data.get("county_resolved") else 60.0

        return BuyerMatch(
            buyer_id=buyer.buyer_id,
            property_id=property_data.get("id", ""),
            match_score=score,
            match_reasons=match_reasons,
            mismatch_reasons=mismatch_reasons,
            evidence=evidence,
            confidence=confidence
        )
