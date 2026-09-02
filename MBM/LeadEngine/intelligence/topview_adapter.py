"""
TopviewAdapter — production engine (§8).

Investigate official API surface before wiring; this adapter is
allow_pending_verification until the API is confirmed live.

Responsibilities: auth, project creation, script submission, video
generation, job polling, status normalization, asset retrieval,
timeout/retry/idempotency, provider quota handling.

Pipeline: IntelligenceEvent -> ContentOpportunity -> Hook -> Script -> Topview Draft -> QA -> Human Approval -> Publishing Queue
"""
from __future__ import annotations

import json
import time
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .provider_policy import assert_allowed
from .jobs import GenerationJob, JobStore, input_hash
from .observability import record, AuditLog

ALLOWED_HOSTS = {"api.topview.ai", "topview.ai", "www.topview.ai"}

class TopviewError(RuntimeError):
    def __init__(self, code: str, msg: str, retryable: bool = False):
        super().__init__(f"[{code}] {msg}")
        self.code = code
        self.retryable = retryable

class TopviewAdapter:
    """
    Adapter for Topview AI video agent.

    If TOPVIEW_API_KEY is unset, all calls return a BLOCKED job instead
    of fabricating a video (per §8: do not claim success without real result).
    """
    def __init__(self, api_key: str = "", base_url: str = "https://api.topview.ai", timeout_sec: float = 15.0, store: Optional[JobStore] = None, audit: Optional[AuditLog] = None):
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "https://api.topview.ai").rstrip("/")
        self.timeout_sec = timeout_sec
        self.store = store or JobStore()
        self.audit = audit or AuditLog()

    def _gate(self) -> None:
        assert_allowed("topview", purpose="production")

    def _headers(self) -> Dict[str, str]:
        h = {"User-Agent": "mbm-intelligence/1.0", "Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def create_generation_job(
        self,
        *,
        hook: str,
        script: str,
        opportunity_id: str = "",
        title: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> GenerationJob:
        """
        Create a Topview generation job. Returns a trackable GenerationJob
        with status QUEUED|BLOCKED. Idempotent on (hook, script, opportunity_id).
        """
        self._gate()
        payload = {"hook": hook, "script": script, "opportunity_id": opportunity_id, "title": title, "metadata": metadata or {}}
        ih = input_hash(payload)
        key = idempotency_key or hashlib.sha256(f"topview|{hook}|{script}|{opportunity_id}".encode()).hexdigest()[:20]

        # dedupe: existing job with same inputHash that is not FAILED/CANCELLED
        for it in self.store.list(provider="topview"):
            if it.get("inputHash") == ih and it.get("status") not in ("FAILED", "CANCELLED"):
                # return existing job object
                j = GenerationJob(id=it["id"], provider="topview", inputHash=ih, status=it["status"], providerJobId=it.get("providerJobId"), attempts=it.get("attempts", 0), createdAt=it.get("createdAt",""), idempotencyKey=it.get("idempotencyKey"), payload=payload, result=it.get("result") or {})
                return j

        job = GenerationJob(
            id=f"tv_{hashlib.sha256(f'{ih}{time.time_ns()}'.encode()).hexdigest()[:12]}",
            provider="topview",
            inputHash=ih,
            status="QUEUED",
            idempotencyKey=key,
            payload=payload,
        )

        if not self.api_key:
            job.status = "BLOCKED"
            job.errorCode = "NOT_CONFIGURED"
            job.errorMessage = "TOPVIEW_API_KEY not configured — job blocked (no mock video generated)"
            self.store.upsert(job)
            self.audit.append("topview.create_job", "topview", status="blocked", detail={"reason": "no api key", "job_id": job.id})
            record("topview", "blocked", 1)
            return job

        # Attempt live submission with bounded retry
        try:
            provider_id = self._submit(payload)
            job.providerJobId = provider_id
            job.status = "RUNNING"
            job.startedAt = datetime.now(timezone.utc).isoformat()
            job.attempts = 1
            self.audit.append("topview.create_job", "topview", status="ok", detail={"job_id": job.id, "provider_job": provider_id})
            record("topview", "requests", 1)
            record("topview", "successes", 1)
        except TopviewError as e:
            job.status = "BLOCKED" if e.code in ("AUTH_FAILED", "BLOCKED") else "FAILED"
            job.errorCode = e.code
            job.errorMessage = str(e)[:500]
            job.attempts = 1
            self.audit.append("topview.create_job", "topview", status=f"failed:{e.code}", detail={"error": str(e)[:400]})
            record("topview", "failures", 1)
            if e.code == "RATE_LIMITED":
                record("topview", "rate_limited", 1)
        except Exception as e:
            job.status = "FAILED"
            job.errorCode = "TRANSIENT"
            job.errorMessage = str(e)[:500]
            job.attempts = 1

        self.store.upsert(job)
        return job

    def _submit(self, payload: Dict[str, Any]) -> str:
        # Try plausible Topview endpoints (API surface still pending verification)
        endpoints = ["/api/v1/videos", "/api/videos", "/api/generate", "/v1/generate"]
        last_err: Optional[TopviewError] = None
        for ep in endpoints:
            url = self.base_url + ep
            host = urllib.parse.urlparse(url).hostname or ""
            if host.lower() not in ALLOWED_HOSTS and "localhost" not in host:
                continue
            body = json.dumps(payload).encode()
            req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as res:
                    if res.status in (200, 201, 202):
                        data = json.loads(res.read().decode("utf-8") or "{}")
                        pid = str(data.get("id") or data.get("job_id") or data.get("video_id") or data.get("task_id") or "")
                        if pid:
                            return pid
                        return f"tv_{hashlib.sha256(body).hexdigest()[:10]}"
                    if res.status == 404:
                        last_err = TopviewError("TRANSIENT", f"{ep} 404", retryable=False)
                        continue
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise TopviewError("AUTH_FAILED", f"HTTP {e.code}")
                if e.code == 429:
                    raise TopviewError("RATE_LIMITED", "HTTP 429", retryable=True)
                if 500 <= e.code < 600:
                    last_err = TopviewError("TRANSIENT", f"HTTP {e.code}", retryable=True)
                    continue
                raise TopviewError("TRANSIENT", f"HTTP {e.code}")
            except Exception as e:
                last_err = TopviewError("TRANSIENT", str(e), retryable=True)
                continue
        raise last_err or TopviewError("TRANSIENT", "No Topview endpoint succeeded", retryable=True)

    def poll_status(self, job_id: str) -> GenerationJob:
        """Poll provider for job status; normalize to QUEUED/RUNNING/SUCCEEDED/FAILED."""
        self._gate()
        data = self.store.get(job_id)
        if not data:
            raise TopviewError("INVALID_INPUT", f"unknown job {job_id}")
        job = GenerationJob(**{k: v for k, v in data.items() if k in GenerationJob.__dataclass_fields__})
        job.payload = data.get("payload") or {}
        job.result = data.get("result") or {}
        if not self.api_key or not job.providerJobId:
            return job
        # Live poll if configured
        for ep in (f"/api/v1/videos/{job.providerJobId}", f"/api/videos/{job.providerJobId}", f"/api/jobs/{job.providerJobId}"):
            url = self.base_url + ep
            req = urllib.request.Request(url, headers=self._headers(), method="GET")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as res:
                    body = json.loads(res.read().decode("utf-8") or "{}")
                    status = str(body.get("status") or body.get("state") or "").lower()
                    if status in ("succeeded", "completed", "done", "finished"):
                        job.status = "SUCCEEDED"
                        job.finishedAt = datetime.now(timezone.utc).isoformat()
                        job.result = body
                    elif status in ("failed", "error"):
                        job.status = "FAILED"
                        job.errorCode = "FAILED"
                        job.errorMessage = str(body.get("error") or "")[:500]
                        job.finishedAt = datetime.now(timezone.utc).isoformat()
                    elif status in ("running", "processing", "queued", "pending"):
                        job.status = "RUNNING" if status != "queued" else "QUEUED"
                    self.store.upsert(job)
                    return job
            except Exception:
                continue
        return job
