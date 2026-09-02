"""M-022 Production Activation Readiness.

This module extends existing MBM-Social YouTube/OAuth infrastructure
(`youtube_api_publisher.py`, `youtube_tokens.json`, `ChannelRegistry.json`).

Safety rules (hard stops):
- uploads BLOCKED until readiness gate passes
- publishes BLOCKED until readiness gate passes
- deletes BLOCKED until readiness gate passes
- updates BLOCKED until readiness gate passes
- no live writes until AUTHENTICATED + CHANNEL_VALID + READY_FOR_CONTROLLED_ACTIVATION

No new isolated project. No TikTok expansion. No Spec-Ad reopening.
"""
from .youtube_oauth_readiness import OAuthReadinessChecker, OAuthState, ScopeStatus
from .channel_health import ChannelHealthChecker, ChannelStatus, ChannelMatrixEntry
from .quota_guard import QuotaGuard, QuotaState
from .dry_run_campaign import DryRunCampaign, DryRunResult
from .upload_policy import UploadPolicy, UploadGate, IdempotencyEngine
from .security_config import SecurityConfig

__version__ = "0.1.0"
