"""MBM-Social multi-channel publishing engine.

Extends (does not replace) the clipping-factory backend. The upstream
pipeline stages (acquire, transcribe, analyze, generate, edit, QC) are the
existing clipping-factory agents; this package adds brand routing, brand-
aware packaging, per-channel publishing, analytics rollup and learning.

Modules:
  model_registry    - Local LLM routing (Ollama)
  brand_config      - Registry + brand YAML loader
  brand_router      - Brand-fit scoring and channel selection
  publish_package   - Build brand-aware title/desc/hashtags/thumb text
  pipeline          - End-to-end publish flow (manual trigger)
  autonomous_runtime - Full autonomous campaign lifecycle orchestrator
  learning_engine   - Self-improving analytics memory + weight adjustment
  night_operations  - Automated overnight maintenance missions
  publisher         - Playwright YouTube Studio publisher
  youtube_api_publisher - YouTube Data API v3 publisher
"""
from . import model_registry, brand_config, brand_router, publish_package
from . import autonomous_runtime, learning_engine, night_operations

__all__ = [
    "model_registry", "brand_config", "brand_router", "publish_package",
    "autonomous_runtime", "learning_engine", "night_operations",
]
