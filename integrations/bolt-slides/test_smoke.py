#!/usr/bin/env python3
"""Hermetic smoke tests for the bolt-slides deck builder (power #8).

No network, no keys, no browser — everything renders in-process and the
MCP server is exercised over stdio against a subprocess.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import deck_builder
from deck_builder import Deck


class TestRendering(unittest.TestCase):
    def test_escape_xss(self):
        marker = "XSS-MARKER-9f2"
        d = Deck(title=f"Hi <script>alert('{marker}')</script>")
        d.add_bullets("T", [f"<img src=x onerror=alert('{marker}')>",
                            "plain"])
        d.add_cta("C", ["<b>bold</b>"], "Go", "https://example.com/?a=<x>")
        h = d.render_html()
        # the payload must never appear raw...
        self.assertNotIn(f"alert('{marker}')", h)
        self.assertNotIn("<img src=x", h)
        # ...but must appear escaped (content preserved, inert)
        self.assertIn("&lt;script&gt;", h)
        self.assertIn("&lt;img", h)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", h)
        self.assertIn("a=&lt;x&gt;", h)

    def test_cover_and_bullets_render(self):
        d = Deck(title="Deck", subtitle="Sub", author="MBM")
        d.add_cover(kicker="KICK", title="Big Title", subtitle="small",
                    cta="keep going")
        d.add_bullets("Points", ["one", "two", "three"])
        h = d.render_html()
        self.assertIn("Big Title", h)
        self.assertIn("KICK", h)
        self.assertIn("<li class=\"build\">one</li>", h)
        self.assertIn("<li class=\"build\">three</li>", h)
        self.assertEqual(h.count('<section class="slide"'), 2)

    def test_widgets_present(self):
        d = Deck(title="W")
        d.add_widget("data_clean_demo", title="Demo")
        d.add_widget("roi_calculator", title="ROI",
                     config={"pilot_price": 499})
        h = d.render_html()
        # data-clean demo widget markers
        self.assertIn("dcClean(this)", h)
        self.assertIn('class="dc-out"', h)
        self.assertIn("function dcClean(btn)", h)
        # roi calculator markers
        self.assertIn('data-roi="hrs"', h)
        self.assertIn('data-roi-out="payback"', h)
        self.assertIn("function roiUpdate(", h)
        self.assertIn("$499", h)

    def test_keyboard_and_nav_js(self):
        d = Deck(title="N")
        d.add_statement("Hello")
        h = d.render_html()
        # navigation handlers
        self.assertIn("ArrowRight", h)
        self.assertIn("ArrowLeft", h)
        self.assertIn("pendingBuilds", h)       # click-to-reveal builds
        self.assertIn("show-notes", h)           # presenter notes toggle
        self.assertIn("requestFullscreen", h)    # F = fullscreen
        self.assertIn('id="progress"', h)
        self.assertIn('id="counter"', h)
        # single-file: no external references
        self.assertNotIn("http://", h.replace("https://example.com", ""))
        self.assertNotIn('src="http', h)
        self.assertNotIn('href="http', h.replace('href="https://example.com', ""))

    def test_chart_validation(self):
        d = Deck(title="C")
        with self.assertRaises(ValueError):
            d.add_chart("Bad", [("a", -1)])
        with self.assertRaises(ValueError):
            d.add_chart("Bad", [("a", "lots")])
        with self.assertRaises(ValueError):
            d.add_chart("Empty", [])
        d.add_chart("OK", [("a", 3), ("b", 0)])
        h = d.render_html()
        self.assertIn('class="chart"', h)
        self.assertIn('class="bar"', h)

    def test_bad_inputs_rejected(self):
        with self.assertRaises(ValueError):
            Deck(title="   ")
        with self.assertRaises(ValueError):
            Deck(title="T", theme="neon")
        d = Deck(title="T")
        with self.assertRaises(ValueError):
            d.add_widget("teleporter")
        with self.assertRaises(ValueError):
            d.add_bullets("T", [])
        with self.assertRaises(ValueError):
            d.add_pricing("P", [{"name": "NoPrice"}])
        with self.assertRaises(ValueError):
            d.add_cta("C", [], "Go", "   ")

    def test_json_roundtrip(self):
        d = Deck(title="RT", theme="paper")
        d.add_cover(kicker="K", title="T")
        d.add_widget("roi_calculator", config={"pilot_price": 297})
        spec = d.to_dict()
        self.assertEqual(spec["title"], "RT")
        self.assertEqual(spec["theme"], "paper")
        self.assertEqual(len(spec["slides"]), 2)
        self.assertEqual(spec["slides"][1]["kind"], "widget")
        self.assertEqual(spec["slides"][1]["payload"]["widget"],
                         "roi_calculator")
        json.dumps(spec)  # must be JSON-serialisable

    def test_export_file(self):
        d = Deck(title="Export me")
        d.add_statement("Hi", sub="there")
        with tempfile.TemporaryDirectory() as td:
            out = d.save(Path(td) / "deck.html")
            text = out.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("<!DOCTYPE html>"))
            self.assertTrue(text.rstrip().endswith("</html>"))
            self.assertIn("<title>Export me</title>", text)


class TestSampleDeck(unittest.TestCase):
    def test_sample_builds(self):
        d = deck_builder.build_dataclean_sample()
        kinds = [s["kind"] for s in d.slides]
        self.assertEqual(
            kinds,
            ["cover", "bullets", "widget", "statement", "widget",
             "chart", "pricing", "cta"])
        widgets = [s["payload"]["widget"] for s in d.slides
                   if s["kind"] == "widget"]
        self.assertEqual(widgets, ["data_clean_demo", "roi_calculator"])
        h = d.render_html()
        self.assertIn("DataClean AI", h)
        self.assertIn("$499", h)
        self.assertIn("clipform.io/7f9689f00", h)

    def test_sample_cli(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "pitch.html"
            rc = subprocess.run(
                [sys.executable, str(HERE / "deck_builder.py"),
                 "--sample", "--out", str(out)],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(rc.returncode, 0, rc.stderr)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 12_000)


class TestMCPProtocol(unittest.TestCase):
    def _session(self):
        proc = subprocess.Popen(
            [sys.executable, str(HERE / "mcp_server.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1)
        self.addCleanup(lambda: (proc.kill(), proc.wait()))
        counter = [0]

        def call(method, params=None):
            msg = {"jsonrpc": "2.0", "method": method}
            is_notification = method.startswith("notifications/")
            if not is_notification:
                counter[0] += 1
                msg["id"] = counter[0]
            if params is not None:
                msg["params"] = params
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            if is_notification:
                return None  # notifications get no response (JSON-RPC)
            return json.loads(proc.stdout.readline())
        return proc, call

    def test_full_flow_over_stdio(self):
        _, call = self._session()
        init = call("initialize", {})
        self.assertEqual(init["result"]["serverInfo"]["name"], "bolt-slides")
        call("notifications/initialized", {})
        tools = call("tools/list", {})
        names = [t["name"] for t in tools["result"]["tools"]]
        self.assertEqual(len(names), 6)
        self.assertIn("deck_export_html", names)

        created = call("tools/call", {
            "name": "deck_create",
            "arguments": {"title": "MCP Deck", "theme": "paper"}})
        deck_id = json.loads(
            created["result"]["content"][0]["text"])["deck_id"]

        added = call("tools/call", {
            "name": "deck_add_slide",
            "arguments": {"deck_id": deck_id, "kind": "widget",
                          "payload": {"widget": "data_clean_demo",
                                      "title": "Live demo"},
                          "notes": "presenter note here"}})
        self.assertEqual(
            json.loads(added["result"]["content"][0]["text"])["slide_index"], 0)

        spec = call("tools/call", {
            "name": "deck_get", "arguments": {"deck_id": deck_id}})
        body = json.loads(spec["result"]["content"][0]["text"])
        self.assertEqual(body["theme"], "paper")
        self.assertEqual(body["slides"][0]["notes"], "presenter note here")

        listed = call("tools/call", {"name": "deck_list", "arguments": {}})
        rows = json.loads(listed["result"]["content"][0]["text"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slides"], 1)

        with tempfile.TemporaryDirectory() as td:
            exported = call("tools/call", {
                "name": "deck_export_html",
                "arguments": {"deck_id": deck_id,
                              "path": str(Path(td) / "mcp-deck.html")}})
            info = json.loads(exported["result"]["content"][0]["text"])
            self.assertTrue(Path(info["path"]).exists())
            self.assertGreater(info["bytes"], 8_000)

        rendered = call("tools/call", {
            "name": "deck_render_html", "arguments": {"deck_id": deck_id}})
        rbody = json.loads(rendered["result"]["content"][0]["text"])
        self.assertIn("<!DOCTYPE html>", rbody["html"])

        # error paths stay inside the protocol
        bad_kind = call("tools/call", {
            "name": "deck_add_slide",
            "arguments": {"deck_id": deck_id, "kind": "teleporter",
                          "payload": {}}})
        self.assertTrue(bad_kind["result"]["isError"])
        bad_deck = call("tools/call", {
            "name": "deck_get", "arguments": {"deck_id": "nope"}})
        self.assertTrue(bad_deck["result"]["isError"])
        unknown = call("tools/call", {
            "name": "nope", "arguments": {}})
        self.assertTrue(unknown["result"]["isError"])
        with self.assertRaises(KeyError):
            call("bogus/method", {})["result"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
