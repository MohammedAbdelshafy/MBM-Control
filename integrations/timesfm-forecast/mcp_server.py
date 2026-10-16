#!/usr/bin/env python3
"""Stdlib-only MCP stdio server for the timesfm-forecast integration.

Tools:
  forecast         Run a forecast on a numeric series (values list).
  forecast_csv     Run a forecast on a CSV string (first numeric column, or named column).
  backend_status   Report which backends are installed on this machine.
  validate_series  Validate a series without forecasting.
  summarize        One-paragraph human summary of a forecast result.
  help             Capability description + activation steps.

Protocol: JSON-RPC 2.0 over stdio. Methods: initialize, tools/list,
tools/call, notifications/initialized (no response). One request per line.
"""

import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import timesfm_forecast as tf

TOOLS = [
    {"name": "forecast", "description": "Forecast next N steps of a numeric series (free, local TimesFM; no key).",
     "inputSchema": {"type": "object", "properties": {
         "values": {"type": "array", "items": {"type": "number"}, "description": "Historical values, >=8 points"},
         "horizon": {"type": "integer", "default": 12, "description": "Steps ahead, 1..512"},
         "quantiles": {"type": "array", "items": {"type": "number"}, "description": "Sorted (0,1), default deciles"},
         "backend": {"type": "string", "enum": ["timesfm", "fake"], "default": "timesfm"},
         "series_name": {"type": "string", "default": "series"},
         "frequency": {"type": "string", "description": "e.g. 'weekly', 'daily' (label only)"}}}},
    {"name": "forecast_csv", "description": "Forecast from CSV text: first numeric column or a named column.",
     "inputSchema": {"type": "object", "properties": {
         "csv": {"type": "string", "description": "CSV text with a header row"},
         "column": {"type": "string", "description": "Column name (default: first numeric column)"},
         "horizon": {"type": "integer", "default": 12},
         "quantiles": {"type": "array", "items": {"type": "number"}},
         "backend": {"type": "string", "enum": ["timesfm", "fake"], "default": "timesfm"},
         "series_name": {"type": "string", "default": "series"},
         "frequency": {"type": "string"}}}},
    {"name": "backend_status", "description": "Check whether the real TimesFM backend is installed here.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "validate_series", "description": "Validate a series without forecasting (returns cleaned values).",
     "inputSchema": {"type": "object", "properties": {
         "values": {"type": "array", "items": {"type": "number"}}}}},
    {"name": "summarize", "description": "Human summary of a forecast result object.",
     "inputSchema": {"type": "object", "properties": {
         "result": {"type": "object", "description": "A forecast() result"}}}},
    {"name": "help", "description": "What this capability is, limits, and how to activate the real backend.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def _parse_csv(csv_text, column=None):
    lines = [ln for ln in csv_text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        raise tf.ForecastError("CSV needs a header row plus at least 8 data rows")
    header = [h.strip() for h in lines[0].split(",")]
    rows = [[c.strip() for c in ln.split(",")] for ln in lines[1:]]
    if column:
        if column not in header:
            raise tf.ForecastError(f"column {column!r} not in header {header}")
        idx = header.index(column)
    else:
        idx = None
        for j in range(len(header)):
            try:
                [float(r[j]) for r in rows]
                idx = j
                break
            except (ValueError, IndexError):
                continue
        if idx is None:
            raise tf.ForecastError("no numeric column found in CSV")
    colname = header[idx]
    vals = []
    for r in rows:
        try:
            vals.append(float(r[idx]))
        except (ValueError, IndexError):
            raise tf.ForecastError(f"non-numeric value in column {colname!r}: {r[idx] if idx < len(r) else ''!r}")
    return vals, colname


def call_tool(name, args):
    args = args or {}
    if name == "forecast":
        return tf.forecast(args["values"], horizon=args.get("horizon", 12),
                           quantiles=args.get("quantiles"), backend=args.get("backend", "timesfm"),
                           series_name=args.get("series_name", "series"),
                           frequency=args.get("frequency"))
    if name == "forecast_csv":
        vals, colname = _parse_csv(args["csv"], args.get("column"))
        return tf.forecast(vals, horizon=args.get("horizon", 12),
                           quantiles=args.get("quantiles"), backend=args.get("backend", "timesfm"),
                           series_name=args.get("series_name") or colname,
                           frequency=args.get("frequency"))
    if name == "backend_status":
        return tf.backend_status()
    if name == "validate_series":
        return {"ok": True, "n": len(tf.validate_series(args["values"]))}
    if name == "summarize":
        return {"ok": True, "summary": tf.summarize(args["result"])}
    if name == "help":
        return {"ok": True, "help": (
            "timesfm-forecast: free, local time-series forecasting via Google's TimesFM "
            "(pretrained foundation model, Apache-2.0, no API key, no network, no per-call cost). "
            "LIMIT: the model sees numbers, not business context — forecasts are baselines, not guarantees. "
            "ACTIVATE the real backend: pip install timesfm torch  (CPU ok), then set TIMESFM_CHECKPOINT "
            "if not using the default HF repo; checkpoint downloads once (~800MB) then runs offline. "
            "Without it, backend='timesfm' raises BackendNotInstalled with install steps; "
            "backend='fake' is a deterministic test double for the smoke tests only.")}
    raise tf.ForecastError(f"unknown tool {name!r}")


def handle(req):
    rid = req.get("id")
    method = req.get("method")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "timesfm-forecast", "version": tf.ADAPTER_VERSION}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = req.get("params", {})
        try:
            out = call_tool(params.get("name"), params.get("arguments"))
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": json.dumps(out)}], "isError": False}}
        except tf.ForecastError as e:
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": "ForecastError: " + str(e)}], "isError": True}}
        except KeyError as e:
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": f"ForecastError: missing argument {e}"}], "isError": True}}
    if method == "notifications/initialized":
        return None  # notification: no response
    if method and method.startswith("notifications/"):
        return None
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(
                {"jsonrpc": "2.0", "id": None,
                 "error": {"code": -32700, "message": "parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
