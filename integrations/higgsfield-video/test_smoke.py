#!/usr/bin/env python3
"""Smoke tests for the Higgsfield video integration — HERMETIC.

No network. No API key. No charge. Network calls are monkeypatched at the
urllib boundary; the MCP server is exercised over a real stdio subprocess.

Run:  python3 test_smoke.py -v
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import hf_client  # noqa: E402
from hf_client import HiggsfieldError, ValidationError  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen_factory(responses):
    """Pop urlopen: each call returns the next scripted payload."""
    state = {"i": 0, "requests": []}

    def fake_urlopen(req, timeout=None):
        state["requests"].append(req)
        idx = state["i"]
        state["i"] += 1
        payload = responses[min(idx, len(responses) - 1)]
        return FakeResponse(payload)

    fake_urlopen.state = state
    return fake_urlopen


class TestCredentials(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        for k in ("HF_API_KEY_ID", "HF_API_KEY_SECRET", "HIGGSFIELD_API_KEY",
                  "HIGGSFIELD_API_BASE"):
            os.environ.pop(k, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_missing_credentials_raise_never_invented(self):
        with self.assertRaises(HiggsfieldError):
            hf_client.resolve_credentials()

    def test_pair_form(self):
        os.environ["HF_API_KEY_ID"] = "kid"
        os.environ["HF_API_KEY_SECRET"] = "ksecret"
        header, base = hf_client.resolve_credentials()
        self.assertEqual(header, "Key kid:ksecret")
        self.assertEqual(base, hf_client.DEFAULT_BASE)

    def test_single_token_form(self):
        os.environ["HIGGSFIELD_API_KEY"] = "tok123"
        header, _ = hf_client.resolve_credentials()
        self.assertEqual(header, "Key tok123")

    def test_base_override(self):
        os.environ["HF_API_KEY_ID"] = "a"
        os.environ["HF_API_KEY_SECRET"] = "b"
        os.environ["HIGGSFIELD_API_BASE"] = "https://example.test/"
        _, base = hf_client.resolve_credentials()
        self.assertEqual(base, "https://example.test")


class TestValidation(unittest.TestCase):
    def test_seedance_t2v_ok(self):
        p = hf_client.validate_input(
            "bytedance/seedance-2.5/text-to-video",
            {"prompt": "a cat in a cinema", "duration": 5})
        self.assertEqual(p["prompt"], "a cat in a cinema")

    def test_missing_required(self):
        with self.assertRaises(ValidationError) as cm:
            hf_client.validate_input("bytedance/seedance-2.5/text-to-video", {})
        self.assertIn("prompt", str(cm.exception))

    def test_unknown_param(self):
        with self.assertRaises(ValidationError):
            hf_client.validate_input(
                "bytedance/seedance-2.5/text-to-video",
                {"prompt": "x", "bogus_param": 1})

    def test_unknown_model(self):
        with self.assertRaises(ValidationError):
            hf_client.validate_input("nope/not-a-model", {"prompt": "x"})

    def test_kling_i2v_requires_image(self):
        with self.assertRaises(ValidationError):
            hf_client.validate_input("kling-video/v3.0-turbo/image-to-video",
                                     {"prompt": "animate it"})


class TestCost(unittest.TestCase):
    def test_seedance_5s(self):
        est = hf_client.estimate_cost("bytedance/seedance-2.5/text-to-video", 5)
        self.assertAlmostEqual(est["estimated_usd"], 0.0738 * 5)

    def test_soul_image_flat(self):
        est = hf_client.estimate_cost("higgsfield-ai/soul/v2/standard")
        self.assertAlmostEqual(est["estimated_usd"], 0.0032)

    def test_kling3_10s(self):
        est = hf_client.estimate_cost("kling-video/v3.0-turbo/image-to-video", 10)
        self.assertAlmostEqual(est["estimated_usd"], 1.12)


class TestSubmitDryRun(unittest.TestCase):
    def test_dry_run_makes_no_network_call(self):
        with mock.patch.object(hf_client.urllib.request, "urlopen") as uo:
            resp = hf_client.submit(
                "bytedance/seedance-2.5/text-to-video",
                {"prompt": "coastal road", "duration": 5}, dry_run=True)
        uo.assert_not_called()
        self.assertTrue(resp["dry_run"])
        self.assertIn("estimate", resp)
        self.assertIn("DRYRUN", resp["request_id"])


class TestSubmitLive(unittest.TestCase):
    def setUp(self):
        os.environ["HF_API_KEY_ID"] = "kid"
        os.environ["HF_API_KEY_SECRET"] = "ksec"

    def tearDown(self):
        os.environ.pop("HF_API_KEY_ID", None)
        os.environ.pop("HF_API_KEY_SECRET", None)

    def test_submit_posts_and_returns_request_id(self):
        fake = fake_urlopen_factory([{
            "request_id": "rid-1", "status": "queued",
            "status_url": "https://platform.higgsfield.ai/requests/rid-1/status",
            "cancel_url": "https://platform.higgsfield.ai/requests/rid-1/cancel"}])
        with mock.patch.object(hf_client.urllib.request, "urlopen", fake):
            resp = hf_client.submit(
                "higgsfield-ai/soul/v2/standard",
                {"prompt": "product photo"}, dry_run=False)
        self.assertEqual(resp["request_id"], "rid-1")
        req = fake.state["requests"][0]
        self.assertTrue(req.full_url.endswith("/higgsfield-ai/soul/v2/standard"))
        self.assertEqual(req.get_header("Authorization"), "Key kid:ksec")

    def test_http_401_surfaces_cleanly(self):
        def boom(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized",
                                         {}, io.BytesIO(b'{"detail":"bad key"}'))

        with mock.patch.object(hf_client.urllib.request, "urlopen", boom):
            with self.assertRaises(HiggsfieldError) as cm:
                hf_client.submit("higgsfield-ai/soul/v2/standard",
                                 {"prompt": "x"}, dry_run=False)
        self.assertIn("401", str(cm.exception))


class TestPolling(unittest.TestCase):
    def test_wait_resolves_through_lifecycle(self):
        seq = [{"status": "queued"}, {"status": "in_progress"},
               {"status": "completed",
                "video": {"url": "https://cdn.test/v.mp4"}}]
        calls = []

        def status_fn(rid):
            calls.append(rid)
            return seq[min(len(calls) - 1, len(seq) - 1)]

        with mock.patch.object(hf_client.time, "sleep", lambda s: None):
            final = hf_client.wait("rid-x", interval=0, max_wait=60,
                                   status_fn=status_fn)
        self.assertEqual(final["status"], "completed")
        media = hf_client.extract_media_urls(final)
        self.assertEqual(media["video_url"], "https://cdn.test/v.mp4")

    def test_wait_raises_on_failure(self):
        with mock.patch.object(hf_client.time, "sleep", lambda s: None):
            with self.assertRaises(HiggsfieldError) as cm:
                hf_client.wait("rid-y", interval=0, max_wait=60,
                               status_fn=lambda rid: {"status": "failed",
                                                      "error": "gpu busy"})
        self.assertIn("failed", str(cm.exception))

    def test_wait_raises_on_nsfw(self):
        with mock.patch.object(hf_client.time, "sleep", lambda s: None):
            with self.assertRaises(HiggsfieldError):
                hf_client.wait("rid-z", interval=0, max_wait=60,
                               status_fn=lambda rid: {"status": "nsfw"})

    def test_wait_times_out(self):
        with mock.patch.object(hf_client.time, "sleep", lambda s: None):
            with self.assertRaises(HiggsfieldError):
                hf_client.wait("rid-t", interval=0, max_wait=0.01,
                               status_fn=lambda rid: {"status": "queued"})

    def test_extract_images(self):
        final = {"status": "completed",
                 "images": [{"url": "https://cdn.test/a.jpg"},
                            {"url": "https://cdn.test/b.jpg"}]}
        media = hf_client.extract_media_urls(final)
        self.assertEqual(media["image_urls"],
                         ["https://cdn.test/a.jpg", "https://cdn.test/b.jpg"])


class TestDownload(unittest.TestCase):
    def test_download_streams_to_disk(self):
        payload = b"\x00\x01" * 40000  # 80 KB

        class Big:
            def read(self, n=-1):
                nonlocal payload
                if not payload:
                    return b""
                chunk, payload = payload[:n], payload[n:]
                return chunk

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "clip.mp4"
            with mock.patch.object(hf_client.urllib.request, "urlopen",
                                   lambda *a, **k: Big()):
                saved = hf_client.download("https://cdn.test/v.mp4", dest)
            self.assertEqual(saved.stat().st_size, 80000)


class TestMCPServer(unittest.TestCase):
    @classmethod
    def _rpc(cls, proc, method, params=None, mid=1):
        msg = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            msg["params"] = params
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    def test_initialize_and_tools_list(self):
        proc = subprocess.Popen(
            [sys.executable, str(HERE / "mcp_server.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            init = self._rpc(proc, "initialize", {}, mid=1)
            self.assertEqual(init["result"]["serverInfo"]["name"],
                             "higgsfield-video")
            tools = self._rpc(proc, "tools/list", {}, mid=2)
            names = {t["name"] for t in tools["result"]["tools"]}
            self.assertTrue({"higgsfield_submit", "higgsfield_status",
                             "higgsfield_catalog", "higgsfield_estimate",
                             "higgsfield_download"} <= names)
            est = self._rpc(proc, "tools/call",
                            {"name": "higgsfield_estimate",
                             "arguments": {"model_id": "bytedance/seedance-2.5/text-to-video",
                                           "seconds": 5}}, mid=3)
            payload = json.loads(est["result"]["content"][0]["text"])
            self.assertAlmostEqual(payload["estimated_usd"], 0.369)
            cat = self._rpc(proc, "tools/call",
                            {"name": "higgsfield_catalog", "arguments": {}},
                            mid=4)
            catalog = json.loads(cat["result"]["content"][0]["text"])
            self.assertGreaterEqual(len(catalog["models"]), 5)
            sub = self._rpc(proc, "tools/call",
                            {"name": "higgsfield_submit",
                             "arguments": {"model_id": "higgsfield-ai/soul/v2/standard",
                                           "input": {"prompt": "studio portrait"},
                                           "dry_run": True}}, mid=5)
            sim = json.loads(sub["result"]["content"][0]["text"])
            self.assertTrue(sim["dry_run"])
            bad = self._rpc(proc, "tools/call",
                            {"name": "higgsfield_submit",
                             "arguments": {"model_id": "nope/x",
                                           "input": {"prompt": "y"},
                                           "dry_run": True}}, mid=6)
            self.assertTrue(bad["result"].get("isError"))
            unknown = self._rpc(proc, "no/such/method", {}, mid=7)
            self.assertIn("error", unknown)
        finally:
            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
