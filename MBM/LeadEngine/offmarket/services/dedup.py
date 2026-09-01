"""Deterministic Property Deduplication."""
from __future__ import annotations
from typing import List, Dict, Any
from ..models import Property, deterministic_property_id, normalize_address

def dedup_properties(props: List[Property]) -> List[Property]:
    seen: Dict[str, Property] = {}
    for p in props:
        key = deterministic_property_id(p.apn, p.county, p.state, p.address)
        if key not in seen:
            p.property_id = key
            seen[key]=p
        else:
            # merge evidence and signals
            existing=seen[key]
            existing.evidence.extend(p.evidence)
            existing.raw_records.extend(p.raw_records)
            # merge signals distinct
            # keep original APN if exists
    return list(seen.values())

def dedup_by_phone(contacts: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    import re
    seen=set()
    out=[]
    for c in contacts:
        digits=re.sub(r"\D","",c.get("phone",""))
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if digits and digits not in seen:
            seen.add(digits)
            out.append(c)
    return out
