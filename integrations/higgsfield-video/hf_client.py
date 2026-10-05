#!/usr/bin/env python3
"""Higgsfield API client — stdlib only, no dependencies.

Wraps the verified Higgsfield API flow:

    POST {base}/{model_id}            -> {request_id, status, status_url, cancel_url}
    GET  {base}/requests/{request_id}/status  -> {status: queued|in_progress|completed|failed|nsfw|cancelled}
    completed -> video.url / images[].url

Auth (environment only, never in code):
    HF_API_KEY_ID + HF_API_KEY_SECRET ->  Authorization: Key {id}:{secret}
    or HIGGSFIELD_API_KEY (single token) -> Authorization: Key {token}

No network happens in dry_run=True mode: payloads are validated against the
model catalog and a simulated submission is returned. All paid calls are
opt-in via live=True / --live.

Verified sources (2026-10-05):
  - API live + pricing: higgsfield.ai/higgsfield-api (official)
  - Request shape + auth + base host: two independent community integrations
    (openit-ai/open-agent-os higgsfield-media-generation; nebula-nodes
    higgsfield skill). Schema re-check against docs.higgsfield.ai advised
    before the first paid generation.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("model_catalog.json")
DEFAULT_BASE = "https://platform.higgsfield.ai"
TERMINAL_OK = "completed"
TERMINAL_BAD = {"failed", "nsfw", "cancelled"}
WAIT_STATUSES = {"queued", "in_progress"}


class HiggsfieldError(RuntimeError):
    pass


class ValidationError(HiggsfieldError):
    pass


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text())


def resolve_credentials(key_id: str | None = None,
                        key_secret: str | None = None,
                        single_token: str | None = None,
                        base_url: str | None = None) -> tuple[str, str]:
    """Return (Authorization header value, base URL) from args or env.

    Raises HiggsfieldError if no credential is present — never invents one.
    """
    key_id = key_id or os.environ.get("HF_API_KEY_ID")
    key_secret = key_secret or os.environ.get("HF_API_KEY_SECRET")
    single_token = single_token or os.environ.get("HIGGSFIELD_API_KEY")
    if key_id and key_secret:
        header = f"Key {key_id}:{key_secret}"
    elif single_token:
        header = f"Key {single_token}"
    else:
        raise HiggsfieldError(
            "No Higgsfield credentials. Set HF_API_KEY_ID + HF_API_KEY_SECRET "
            "(or HIGGSFIELD_API_KEY for a single token) in the environment. "
            "Keys are issued at console.higgsfield.ai."
        )
    base = base_url or os.environ.get("HIGGSFIELD_API_BASE") or DEFAULT_BASE
    return header, base.rstrip("/")


def _model_entry(catalog: dict, model_id: str) -> dict:
    for m in catalog["models"]:
        if m["model_id"] == model_id:
            return m
    known = sorted(m["model_id"] for m in catalog["models"])
    raise ValidationError(f"Unknown model_id {model_id!r}. Known: {known}")


def validate_input(model_id: str, params: dict, catalog: dict | None = None) -> dict:
    """Validate params against the catalog schema. Returns normalized params.

    Raises ValidationError with a human-readable reason — nothing is sent.
    """
    catalog = catalog or load_catalog()
    entry = _model_entry(catalog, model_id)
    schema = entry.get("schema", {})
    params = dict(params or {})
    missing = [k for k in schema.get("required", []) if k not in params]
    if missing:
        raise ValidationError(
            f"{model_id} requires: {missing}. Got keys: {sorted(params)}"
        )
    allowed = set(schema.get("required", [])) | set(schema.get("optional", []))
    extra = sorted(k for k in params if k not in allowed)
    if extra:
        raise ValidationError(
            f"{model_id} does not accept: {extra}. Allowed: {sorted(allowed)}"
        )
    return params


def estimate_cost(model_id: str, seconds: float = 5.0,
                  catalog: dict | None = None) -> dict:
    """Pre-flight cost estimate in USD. Never touches the network."""
    catalog = catalog or load_catalog()
    entry = _model_entry(catalog, model_id)
    if entry["kind"] == "image":
        cost = float(entry["price_usd_per_image"])
        return {"model_id": model_id, "kind": "image",
                "estimated_usd": round(cost, 4), "basis": "per image"}
    cost = float(entry["price_usd_per_sec"]) * float(seconds)
    return {"model_id": model_id, "kind": "video",
            "estimated_usd": round(cost, 4),
            "basis": f"{entry['price_usd_per_sec']}/sec x {seconds}s"}


def _http(method: str, url: str, auth_header: str,
          payload: dict | None = None, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", auth_header)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()[:500]
        except Exception:
            body = ""
        raise HiggsfieldError(f"HTTP {e.code} on {method} {url}: {body}") from e
    except urllib.error.URLError as e:
        raise HiggsfieldError(f"Network error on {method} {url}: {e}") from e


def submit(model_id: str, params: dict, *,
           dry_run: bool = False,
           key_id: str | None = None, key_secret: str | None = None,
           single_token: str | None = None,
           base_url: str | None = None) -> dict:
    """Validate + submit a generation. Returns the API response.

    dry_run=True performs full validation and returns a simulated response
    with dry_run=true. NO network, NO charge.
    """
    catalog = load_catalog()
    params = validate_input(model_id, params, catalog)
    estimate = estimate_cost(model_id, params.get("duration", 5), catalog)
    if dry_run:
        return {"request_id": "DRYRUN-00000000-0000-0000-0000-000000000000",
                "status": "queued", "model_id": model_id,
                "validated_input": params, "estimate": estimate,
                "dry_run": True,
                "note": "No network call made. Set dry_run=False to submit live."}
    auth, base = resolve_credentials(key_id, key_secret, single_token, base_url)
    resp = _http("POST", f"{base}/{model_id}", auth, payload={"input": params})
    resp["estimate"] = estimate
    return resp


def job_status(request_id: str, *,
               key_id: str | None = None, key_secret: str | None = None,
               single_token: str | None = None,
               base_url: str | None = None) -> dict:
    auth, base = resolve_credentials(key_id, key_secret, single_token, base_url)
    return _http("GET", f"{base}/requests/{request_id}/status", auth)


def wait(request_id: str, *, interval: int = 5, max_wait: int = 900,
         key_id: str | None = None, key_secret: str | None = None,
         single_token: str | None = None,
         base_url: str | None = None,
         status_fn=None) -> dict:
    """Poll until a terminal status. status_fn injectable for tests."""
    status_fn = status_fn or (lambda rid: job_status(
        rid, key_id=key_id, key_secret=key_secret,
        single_token=single_token, base_url=base_url))
    deadline = time.time() + max_wait
    last = {}
    while time.time() < deadline:
        last = status_fn(request_id)
        status = str(last.get("status", "")).lower()
        if status == TERMINAL_OK:
            return last
        if status in TERMINAL_BAD:
            raise HiggsfieldError(
                f"Job {request_id} ended with status={status}: "
                f"{last.get('error', last)}")
        if status not in WAIT_STATUSES and status:
            raise HiggsfieldError(
                f"Job {request_id}: unexpected status {status!r}: {last}")
        time.sleep(interval)
    raise HiggsfieldError(
        f"Job {request_id} did not complete within {max_wait}s; last={last}")


def download(url: str, dest: str | Path, timeout: int = 120) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp, \
                open(dest, "wb") as fh:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
    except Exception as e:
        raise HiggsfieldError(f"Download failed for {url}: {e}") from e
    return dest


def extract_media_urls(final_status: dict) -> dict:
    """Pull result URLs from a completed job status payload."""
    out: dict = {"video_url": None, "image_urls": []}
    video = final_status.get("video") or {}
    if isinstance(video, dict) and video.get("url"):
        out["video_url"] = video["url"]
    images = final_status.get("images") or []
    for img in images:
        if isinstance(img, dict) and img.get("url"):
            out["image_urls"].append(img["url"])
    return out


if __name__ == "__main__":  # pragma: no cover — convenience CLI
    import argparse
    ap = argparse.ArgumentParser(description="Higgsfield API helper (stdlib only)")
    ap.add_argument("--model", default="bytedance/seedance-2.5/text-to-video")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--seconds", type=float, default=5)
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--image-url", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="validate only, no charge (default)")
    ap.add_argument("--live", action="store_true",
                    help="actually submit (charges your balance)")
    ap.add_argument("--wait", action="store_true",
                    help="poll until completion (live only)")
    args = ap.parse_args()

    params = {"prompt": args.prompt, "aspect_ratio": args.aspect,
              "duration": args.seconds}
    if args.image_url:
        params["image_url" if len(args.image_url) == 1 else "image_urls"] = \
            args.image_url[0] if len(args.image_url) == 1 else args.image_url

    dry = not args.live
    result = submit(args.model, params, dry_run=dry)
    print(json.dumps(result, indent=2))
    if args.live and args.wait and not result.get("dry_run"):
        final = wait(result["request_id"])
        print(json.dumps({"final": final,
                          "media": extract_media_urls(final)}, indent=2))
