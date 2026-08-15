"""ownership_verifier -- authoritative ownership verification + evidence.

Interfaces:
  OwnershipVerifier (ABC)      -- any authoritative/authorized owner source
  ArcGisAssessorAdapter        -- generic county ArcGIS REST parcel adapter
  CountyRoutedVerifier         -- routes property -> county -> adapter
  verify_ownership()           -- one-call convenience

Rules (jarvis-mbm#23):
  - A person/entity is only labelled owner when the source returned it.
  - A person merely associated with an address is never assumed the legal owner.
  - Every assertion carries provenance + verification_status + confidence.
  - No adapter for the county  -> NOT_FOUND, REQUIRES_VERIFICATION (never guess).
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Optional

from .normalize import normalize_street, split_address_parts
from .schema import OwnershipVerification, SourceRef, classify_owner_type

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
DEFAULT_TIMEOUT = 12


def arcgis_query(
    endpoint: str,
    where: str,
    out_fields: str,
    limit: int = 10,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 1,
) -> list[dict]:
    """Query an ArcGIS REST layer. Returns list of feature attribute dicts."""
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "false",
        "resultRecordCount": str(limit),
        "f": "json",
    })
    url = endpoint.rstrip("/") + "/query?" + params
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            if data.get("error"):
                raise RuntimeError(f"arcgis error: {data['error']}")
            return [f.get("attributes", {}) for f in data.get("features", [])]
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt == retries - 1:
                break
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"arcgis query failed: {last_err}") from last_err


def _address_match_score(feature_addr: str, number: str, first_word: str, full: str) -> float:
    """Score how well a source's site address matches the requested address."""
    if not feature_addr:
        return 0.0
    fa = normalize_street(feature_addr)
    req = normalize_street(full)
    if req and fa == req:
        return 5.0
    score = 0.0
    if number and fa.startswith(number):
        score += 2.0
    if first_word and re.search(rf"\b{re.escape(first_word)}\b", fa, re.IGNORECASE):
        score += 2.0
    req_words = set(normalize_street(full).split())
    fa_words = set(fa.split())
    overlap = len(req_words & fa_words)
    score += min(overlap, 2) * 0.5
    return score


def _join_owner(*names: Any) -> str:
    return " & ".join(str(n).strip() for n in names if n and str(n).strip()) or ""


class OwnershipVerifier(ABC):
    """Interface implemented by every ownership source adapter."""

    name: str = "unknown"
    source_url: str = ""

    @abstractmethod
    def verify(self, rec: dict) -> Optional[OwnershipVerification]:
        """Verify ownership for a normalized property dict. Never invents."""


class ArcGisAssessorAdapter(OwnershipVerifier):
    """Generic county assessor adapter over a public ArcGIS REST parcel layer.

    `fields` maps logical names to the layer's attribute names (see
    county_sources.COUNTY_SOURCES for per-county field maps):
      address / address_num / owner1..3 / mailing / mail_city / mail_state /
      mail_zip / parcel / site_city / site_zip
    """

    def __init__(self, name: str, endpoint: str, fields: dict, source_url: str = ""):
        self.name = name
        self.endpoint = endpoint
        self.fields = fields or {}
        self.source_url = source_url or endpoint

    # ── query building ────────────────────────────────────────────────────
    def _where_clauses(self, number: str, street: str) -> list[str]:
        fld = self.fields.get("address")
        num_fld = self.fields.get("address_num") or fld
        first = (street.split()[0] if street else "").strip()
        clauses: list[str] = []
        if fld and number and first:
            clauses.append(
                f"UPPER({fld}) LIKE UPPER('%{number}% {first}%')"
            )
        if num_fld and fld and number and first:
            clauses.append(
                f"UPPER({num_fld}) LIKE UPPER('%{number}%') "
                f"AND UPPER({fld}) LIKE UPPER('%{first}%')"
            )
        return clauses

    def _out_fields(self) -> str:
        wanted = [
            self.fields.get("address"),
            self.fields.get("address_num"),
            self.fields.get("owner1"),
            self.fields.get("owner2"),
            self.fields.get("owner3"),
            self.fields.get("mailing"),
            self.fields.get("mail_city"),
            self.fields.get("mail_state"),
            self.fields.get("mail_zip"),
            self.fields.get("parcel"),
            self.fields.get("site_city"),
            self.fields.get("site_zip"),
        ]
        return ",".join(dict.fromkeys(w for w in wanted if w))

    def _feature_site_address(self, attrs: dict) -> str:
        name = attrs.get(self.fields.get("address")) or ""
        num = attrs.get(self.fields.get("address_num")) or ""
        if num:
            return f"{str(num).strip()} {str(name).strip()}".strip()
        return str(name or "").strip()

    # ── verification ───────────────────────────────────────────────────────
    def verify(self, rec: dict) -> Optional[OwnershipVerification]:
        address = str(rec.get("address") or "").strip()
        if not address:
            return OwnershipVerification(
                property_key=rec.get("dedupe_key") or address,
                source=self.name,
                source_url=self.source_url,
                verification_status="NOT_FOUND",
                confidence=0.0,
                evidence=[],
            )
        parts = split_address_parts(address)
        number = parts["address"].split()[0] if parts["address"] else ""
        street = " ".join(parts["address"].split()[1:]) if parts["address"] else ""

        # Parcel-first lookup when APN present on the record (exact identity).
        parcel = str(rec.get("parcel_id") or "").strip().upper()
        if parcel and self.fields.get("parcel"):
            try:
                feats = arcgis_query(
                    self.endpoint,
                    f"UPPER({self.fields['parcel']}) = UPPER('{parcel}')",
                    self._out_fields(),
                )
                if feats:
                    return self._build(rec, feats, parcel_lookup=True)
            except RuntimeError:
                pass  # fall through to address lookup

        # Address lookup: score ALL candidates, then let _build decide whether
        # the match is unique enough to name an owner (VERIFIED/LIKELY) or
        # ambiguous (CONFLICT). Never assume a person is the legal owner.
        candidates: list[tuple[float, dict]] = []
        clauses = self._where_clauses(number, street)
        for clause in clauses:
            try:
                feats = arcgis_query(self.endpoint, clause, self._out_fields())
            except RuntimeError:
                continue
            for attrs in feats:
                score = _address_match_score(
                    self._feature_site_address(attrs), number, street, address
                )
                candidates.append((score, attrs))
        if not candidates:
            return OwnershipVerification(
                property_key=rec.get("dedupe_key") or address,
                source=self.name,
                source_url=self.source_url,
                verification_status="NOT_FOUND",
                confidence=0.0,
                evidence=[],
                raw={"query": clauses},
            )
        best_score = max(s for s, _ in candidates)
        feats = [a for _, a in candidates]
        scores = [s for s, _ in candidates]
        return self._build(rec, feats, match_score=best_score, scores=scores)

    def _build(
        self,
        rec: dict,
        feats: list[dict],
        match_score: float = 5.0,
        parcel_lookup: bool = False,
        scores: Optional[list[float]] = None,
    ) -> OwnershipVerification:
        """Decide verification status from the candidate features.

        Ambiguity rule: if multiple DISTINCT owners match the same site address
        with a strong score, the result is CONFLICT (no owner is asserted).
        A single owner only yields VERIFIED/LIKELY.
        """
        if not feats:
            return OwnershipVerification(
                property_key=rec.get("dedupe_key") or (rec.get("address") or ""),
                source=self.name,
                source_url=self.source_url,
                verification_status="NOT_FOUND",
                confidence=0.0,
                evidence=[],
            )

        def owner_of(attrs: dict) -> str:
            return _join_owner(
                attrs.get(self.fields.get("owner1")),
                attrs.get(self.fields.get("owner2")),
                attrs.get(self.fields.get("owner3")),
            )

        # Strongly-matched candidates (exact address or APN lookup).
        strong = feats
        if scores is not None and not parcel_lookup:
            strong = [a for a, s in zip(feats, scores) if s >= 4.0] or feats
        distinct_owners = sorted({owner_of(a) for a in strong})
        owner = distinct_owners[0] if len(distinct_owners) == 1 else ""

        # Evidence must point at the feature that produced the asserted owner,
        # never at a weaker candidate (avoids owner/evidence contradictions).
        owner_feats = [a for a in strong if owner_of(a) == owner] or strong
        site_feat = owner_feats[0]
        site = self._feature_site_address(site_feat)
        parcel = str(site_feat.get(self.fields.get("parcel")) or "").strip()
        ambiguous = len(distinct_owners) > 1

        if owner and not ambiguous:
            if parcel_lookup:
                status, confidence = "VERIFIED", 0.95
            elif match_score >= 4.0:
                status, confidence = "VERIFIED", 0.95 if parcel else 0.85
            elif match_score >= 2.0:
                status, confidence = "LIKELY", 0.60
            else:
                status, confidence = "CONFLICT", 0.25
        elif ambiguous:
            # Multiple distinct owners claim the same address: ambiguous.
            status, confidence = "CONFLICT", 0.25
        else:
            status, confidence = "NOT_FOUND", 0.0

        evidence = SourceRef(
            source=self.name,
            source_url=self.source_url,
            source_date="",
            verification_status=status,
            confidence="high" if confidence >= 0.85 else "medium" if confidence >= 0.5 else "low",
            note=(
                f"site_address={site or 'unknown'}; parcel_lookup={parcel_lookup}; "
                f"distinct_owners={len(distinct_owners)}"
            ),
            evidence_payload=site_feat,
        )

        return OwnershipVerification(
            property_key=rec.get("dedupe_key") or (rec.get("address") or ""),
            owner_name=owner,
            owner_type=classify_owner_type(owner),
            parcel_id=parcel,
            site_address=site,
            mailing_address=str(site_feat.get(self.fields.get("mailing")) or "").strip(),
            source=self.name,
            source_url=self.source_url,
            verification_status=status,
            confidence=confidence,
            evidence=[evidence],
            raw={"match_score": match_score, "features": feats},
        )


class CountyRoutedVerifier(OwnershipVerifier):
    """Routes a property to its county's registered adapter."""

    name = "county-routed"

    def __init__(self, registry: Optional[dict] = None):
        self._registry = registry or {}

    def _adapter_for(self, state: str, county: str) -> Optional[OwnershipVerifier]:
        src = self._registry.get((state.upper(), county.title()))
        if not src:
            from .county_registry import route_property

            routed = route_property({"state": state, "county": county})
            src = routed.get("source")
        if not src or src.get("adapter") != "arcgis":
            return None
        return ArcGisAssessorAdapter(
            name=f"{src['county']} {src['authority']}".strip(),
            endpoint=src["api_url"],
            fields=src["fields"],
            source_url=src.get("website_url") or src["api_url"],
        )

    def verify(self, rec: dict) -> Optional[OwnershipVerification]:
        state = str(rec.get("state") or "").strip().upper()
        county = str(rec.get("county") or "").strip().title()
        adapter = self._adapter_for(state, county)
        if adapter is None:
            return OwnershipVerification(
                property_key=rec.get("dedupe_key") or (rec.get("address") or ""),
                source="county-routed",
                source_url="",
                verification_status="NOT_FOUND",
                confidence=0.0,
                evidence=[
                    SourceRef(
                        source="county-routed",
                        source_url="",
                        verification_status="NOT_FOUND",
                        confidence="low",
                        note=f"no verified adapter for {county or 'unknown county'} {state}",
                    )
                ],
            )
        try:
            return adapter.verify(rec)
        except RuntimeError as exc:
            return OwnershipVerification(
                property_key=rec.get("dedupe_key") or (rec.get("address") or ""),
                source=adapter.name,
                source_url=adapter.source_url,
                verification_status="NOT_FOUND",
                confidence=0.0,
                evidence=[
                    SourceRef(
                        source=adapter.name,
                        source_url=adapter.source_url,
                        verification_status="NOT_FOUND",
                        confidence="low",
                        note=f"lookup failed: {exc}",
                    )
                ],
            )


def build_registry_from_sources() -> dict:
    """Build adapter registry from county_sources (verified ArcGIS only)."""
    from .county_sources import COUNTY_SOURCES

    return {
        (s["state"].upper(), s["county"].title()): s
        for s in COUNTY_SOURCES
        if s.get("adapter") == "arcgis"
    }


def verify_ownership(rec: dict, live: bool = True) -> OwnershipVerification:
    """One-call ownership verification for a normalized property dict.

    live=False returns NOT_FOUND (REQUIRES_VERIFICATION) without network so the
    pipeline can run offline safely.
    """
    if not live:
        return OwnershipVerification(
            property_key=rec.get("dedupe_key") or (rec.get("address") or ""),
            source="offline",
            source_url="",
            verification_status="NOT_FOUND",
            confidence=0.0,
            evidence=[
                SourceRef(
                    source="offline",
                    source_url="",
                    verification_status="NOT_FOUND",
                    confidence="low",
                    note="live ownership verification disabled",
                )
            ],
        )
    verifier = CountyRoutedVerifier(build_registry_from_sources())
    return verifier.verify(rec)


def apply_verification(rec: dict, verification: OwnershipVerification) -> dict:
    """Annotate a property dict with ownership evidence (no mutation of truth)."""
    out = dict(rec)
    out["owner_name"] = verification.owner_name
    out["owner_type"] = verification.owner_type
    out["ownership_status"] = verification.verification_status
    out["ownership_confidence"] = verification.confidence
    out["ownership_source"] = verification.source
    out["ownership_source_url"] = verification.source_url
    out["parcel_id"] = verification.parcel_id or rec.get("parcel_id") or ""
    out["ownership_verified_at"] = verification.retrieved_at
    out["ownership_evidence"] = [e.to_dict() for e in verification.evidence]
    return out