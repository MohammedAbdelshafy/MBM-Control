"""MBM-Social multi-channel publishing engine.

Extends (does not replace) the clipping-factory backend. The upstream
pipeline stages (acquire, transcribe, analyze, generate, edit, QC) are the
existing clipping-factory agents; this package adds brand routing, brand-
aware packaging, per-channel publishing, analytics rollup and learning.
"""
from . import model_registry, brand_config, brand_router, publish_package

__all__ = ["model_registry", "brand_config", "brand_router", "publish_package"]
