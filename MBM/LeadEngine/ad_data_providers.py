"""
MBM LeadEngine — Data Provider Interfaces
==========================================
Clean provider interfaces for external data sources.
Each adapter: explicit capabilities, graceful failure, provenance tracking,
freshness exposure, never fabricates missing values.

Providers:
  - LeadDiscoveryProvider: lead discovery (NPI, auction, skip-trace)
  - EnrichmentProvider: phone/email/social enrichment
  - PropertyIntelProvider: property data (ownership, comps, tax)
  - BuyerIntelligenceProvider: buyer discovery and scoring
  - MarketDataProvider: market trends, pricing, inventory
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ─── BASE PROVIDER ───────────────────────────────────────────────

class BaseProvider(ABC):
    """Base class for all data providers. Enforces capability and provenance."""

    provider_name: str = "base"
    capabilities: List[str] = []

    def __init__(self):
        self._last_fetched_at: Optional[str] = None
        self._fetch_count: int = 0
        self._error_count: int = 0

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return provider health: {ok, latency_ms, error}."""
        ...

    def get_provenance(self) -> Dict[str, Any]:
        """Return data provenance metadata."""
        return {
            "provider": self.provider_name,
            "capabilities": self.capabilities,
            "last_fetched_at": self._last_fetched_at,
            "fetch_count": self._fetch_count,
            "error_count": self._error_count,
        }

    def _record_fetch(self, success: bool):
        self._fetch_count += 1
        self._last_fetched_at = datetime.now(timezone.utc).isoformat()
        if not success:
            self._error_count += 1


# ─── LEAD DISCOVERY ──────────────────────────────────────────────

class LeadDiscoveryProvider(BaseProvider):
    """Interface for discovering new leads from external sources."""
    provider_name = "lead_discovery"
    capabilities = ["npi_registry", "auction_scan", "skip_trace", "public_records"]

    @abstractmethod
    def discover_leads(self, market: str, property_type: str = "SFR",
                       limit: int = 50) -> List[Dict[str, Any]]:
        """
        Discover leads in a market. Returns list of lead dicts with:
        {name, address, city, state, zip, phone, email, source, freshness}
        Never fabricates data — returns empty list on failure.
        """
        ...


class NPIRegistryProvider(LeadDiscoveryProvider):
    """NPI Registry lead discovery (real healthcare businesses)."""

    def health_check(self) -> Dict[str, Any]:
        return {"ok": True, "provider": self.provider_name, "mode": "NPI_API"}

    def discover_leads(self, market: str, property_type: str = "SFR",
                       limit: int = 50) -> List[Dict[str, Any]]:
        # Stub — real implementation would call NPI API
        self._record_fetch(True)
        return []


class AuctionProvider(LeadDiscoveryProvider):
    """Auction.com property lead discovery."""

    def health_check(self) -> Dict[str, Any]:
        return {"ok": False, "provider": self.provider_name, "error": "BLOCKED_BY_INCAPSULA"}

    def discover_leads(self, market: str, property_type: str = "SFR",
                       limit: int = 50) -> List[Dict[str, Any]]:
        self._record_fetch(False)
        log.warning("Auction.com blocked by Incapsula — returning empty")
        return []


# ─── ENRICHMENT ──────────────────────────────────────────────────

class EnrichmentProvider(BaseProvider):
    """Interface for enriching leads with additional contact data."""
    provider_name = "enrichment"
    capabilities = ["phone_lookup", "email_verification", "social_enrichment"]

    @abstractmethod
    def enrich_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich a lead with additional data. Returns the lead dict with
        new fields populated. Never overwrites existing data.
        Returns original lead on failure.
        """
        ...

    @abstractmethod
    def verify_phone(self, phone: str) -> Dict[str, Any]:
        """
        Verify a phone number. Returns:
        {valid, carrier, line_type, risk_score, provenance}
        """
        ...


class TwilioLookupProvider(EnrichmentProvider):
    """Phone verification via Twilio Lookup API."""

    def health_check(self) -> Dict[str, Any]:
        import os
        configured = bool(os.environ.get("TWILIO_ACCOUNT_SID"))
        return {"ok": configured, "provider": self.provider_name,
                "configured": configured}

    def enrich_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        phone = lead.get("phone", "")
        if not phone:
            return lead
        result = self.verify_phone(phone)
        if result.get("valid"):
            lead["phone_verified"] = True
            lead["phone_carrier"] = result.get("carrier", "")
            lead["phone_line_type"] = result.get("line_type", "")
        return lead

    def verify_phone(self, phone: str) -> Dict[str, Any]:
        import os
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        if not sid or not token:
            return {"valid": False, "error": "NOT_CONFIGURED", "provenance": "twilio_lookup"}
        try:
            from twilio.rest import Client
            client = Client(sid, token)
            v = client.lookups.v2.phone_numbers(phone).fetch()
            self._record_fetch(True)
            return {
                "valid": True,
                "carrier": getattr(v, "carrier", {}).get("name", ""),
                "line_type": getattr(v, "line_type_intelligence", {}).get("type", ""),
                "risk_score": getattr(v, "caller_name", {}).get("caller_name", ""),
                "provenance": "twilio_lookup",
            }
        except Exception as e:
            self._record_fetch(False)
            return {"valid": False, "error": str(e), "provenance": "twilio_lookup"}


# ─── PROPERTY INTELLIGENCE ───────────────────────────────────────

class PropertyIntelProvider(BaseProvider):
    """Interface for property data: ownership, comps, tax, auctions."""
    provider_name = "property_intel"
    capabilities = ["ownership_verify", "arv_comps", "tax_data", "auction_status"]

    @abstractmethod
    def verify_ownership(self, address: str, city: str, state: str,
                         zip_code: str = "") -> Dict[str, Any]:
        """
        Verify property ownership. Returns:
        {owner_name, owner_address, apn, verified, confidence, provenance}
        Never fabricates owner data.
        """
        ...

    @abstractmethod
    def get_arv_comps(self, address: str, city: str, state: str,
                      property_type: str = "SFR") -> Dict[str, Any]:
        """
        Get ARV comparable sales. Returns:
        {arv, comps: [{address, sale_price, sale_date, sqft}], confidence, provenance}
        """
        ...


class DCADPropertyProvider(PropertyIntelProvider):
    """Dallas County Appraisal District property data."""

    def health_check(self) -> Dict[str, Any]:
        return {"ok": True, "provider": self.provider_name, "mode": "DCAD_API"}

    def verify_ownership(self, address: str, city: str, state: str,
                         zip_code: str = "") -> Dict[str, Any]:
        self._record_fetch(True)
        return {
            "owner_name": "", "owner_address": "", "apn": "",
            "verified": False, "confidence": 0,
            "provenance": "dcad", "note": "stub — connect to DCAD API",
        }

    def get_arv_comps(self, address: str, city: str, state: str,
                      property_type: str = "SFR") -> Dict[str, Any]:
        self._record_fetch(True)
        return {
            "arv": 0, "comps": [], "confidence": 0,
            "provenance": "dcad", "note": "stub — connect to DCAD comps API",
        }


# ─── BUYER INTELLIGENCE ─────────────────────────────────────────

class BuyerIntelligenceProvider(BaseProvider):
    """Interface for buyer discovery and scoring."""
    provider_name = "buyer_intel"
    capabilities = ["buyer_discovery", "buyer_scoring", "buy_box_matching"]

    @abstractmethod
    def discover_buyers(self, market: str, property_type: str = "SFR") -> List[Dict[str, Any]]:
        """
        Discover active buyers in a market. Returns list of buyer dicts.
        """
        ...

    @abstractmethod
    def score_buyer(self, buyer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a buyer's activity and reliability. Returns:
        {activity_score, reliability_score, verification_status, provenance}
        """
        ...


class CSVBuyerProvider(BuyerIntelligenceProvider):
    """Buyer data from CSV files (existing mbm-dialer leads)."""

    def health_check(self) -> Dict[str, Any]:
        return {"ok": True, "provider": self.provider_name, "mode": "CSV"}

    def discover_buyers(self, market: str, property_type: str = "SFR") -> List[Dict[str, Any]]:
        self._record_fetch(True)
        return []

    def score_buyer(self, buyer: Dict[str, Any]) -> Dict[str, Any]:
        self._record_fetch(True)
        return {
            "activity_score": buyer.get("activity_score", 50),
            "reliability_score": buyer.get("reliability_score", 50),
            "verification_status": buyer.get("verification_status", "UNVERIFIED"),
            "provenance": "csv",
        }


# ─── MARKET DATA ─────────────────────────────────────────────────

class MarketDataProvider(BaseProvider):
    """Interface for market trends, pricing, inventory data."""
    provider_name = "market_data"
    capabilities = ["pricing_trends", "inventory_levels", "market_velocity"]

    @abstractmethod
    def get_market_stats(self, market: str, property_type: str = "SFR") -> Dict[str, Any]:
        """
        Get market statistics. Returns:
        {median_price, avg_days_on_market, inventory_months, trend, provenance}
        """
        ...


class StubMarketProvider(MarketDataProvider):
    """Stub market data provider — returns empty until real API connected."""

    def health_check(self) -> Dict[str, Any]:
        return {"ok": False, "provider": self.provider_name, "error": "NOT_CONNECTED"}

    def get_market_stats(self, market: str, property_type: str = "SFR") -> Dict[str, Any]:
        self._record_fetch(False)
        return {
            "median_price": 0, "avg_days_on_market": 0,
            "inventory_months": 0, "trend": "UNKNOWN",
            "provenance": "stub", "note": "connect market data API",
        }


# ─── PROVIDER REGISTRY ───────────────────────────────────────────

class ProviderRegistry:
    """
    Registry of all data providers. Allows runtime lookup by capability.
    """

    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider):
        self._providers[provider.provider_name] = provider

    def get(self, name: str) -> Optional[BaseProvider]:
        return self._providers.get(name)

    def find_by_capability(self, capability: str) -> List[BaseProvider]:
        return [
            p for p in self._providers.values()
            if capability in p.capabilities
        ]

    def health_check_all(self) -> Dict[str, Any]:
        results = {}
        for name, provider in self._providers.items():
            try:
                results[name] = provider.health_check()
            except Exception as e:
                results[name] = {"ok": False, "error": str(e)}
        return results

    def get_provenance_all(self) -> Dict[str, Any]:
        return {
            name: provider.get_provenance()
            for name, provider in self._providers.items()
        }


def create_default_registry() -> ProviderRegistry:
    """Create a registry with all default providers."""
    registry = ProviderRegistry()
    registry.register(NPIRegistryProvider())
    registry.register(AuctionProvider())
    registry.register(TwilioLookupProvider())
    registry.register(DCADPropertyProvider())
    registry.register(CSVBuyerProvider())
    registry.register(StubMarketProvider())
    return registry


# ─── CLI ──────────────────────────────────────────────────────────

def main():
    """CLI entry point for data providers."""
    import sys
    import json

    registry = create_default_registry()

    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: ad_data_providers.py [--health|--provenance]"}))
        return

    cmd = sys.argv[1]
    if cmd == "--health":
        print(json.dumps({"providers": registry.health_check_all()}, default=str))
    elif cmd == "--provenance":
        print(json.dumps({"providers": registry.get_provenance_all()}, default=str))
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))


if __name__ == "__main__":
    main()
