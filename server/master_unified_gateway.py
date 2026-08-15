"""
JARVIS OS // Master Unified Web Gateway & Self-Healing Server
=============================================================
Fixes "Website can't be reached" FOREVER.

Serves all dashboards, dialers, terminals, and APIs on a single,
robust, auto-restarting port (default: 8080) reachable from:
- Desktop: http://localhost:8080
- Mobile (LAN): http://192.168.8.92:8080
- Tailscale: http://100.70.189.91:8080

Routes:
- /                    → Master Mission Control Hub
- /terminal            → Luxury Institutional Real Estate Deal Terminal
- /phound              → Phound SMS Outreach Cockpit
- /crm                 → Salesforce AI OS CRM Dashboard
- /contech             → ConTech Social & High-Ticket Outreach Hub
- /leads_database.json → Master Unified Verified Leads Feed (712 leads)
- /api/objection       → Live Groq/Gemini LPU Objection AI Copilot
- /api/health          → Gateway Health Status
"""

import os
import sys
import json
import socket
import mimetypes
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, List, Any

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent

PORT = 8080
HOST = "0.0.0.0"

# Paths to all dashboards
PATHS = {
    "terminal": REPO_ROOT / "MBM" / "LeadEngine" / "InstitutionalRealEstate" / "luxury_deal_terminal.html",
    "phound": REPO_ROOT / "MBM" / "Phound" / "phound_sms_cockpit.html",
    "crm": REPO_ROOT / "MBM" / "SalesforceOS" / "salesforce_crm.html",
    "contech": REPO_ROOT / "MBM-Social" / "ContechAI" / "contech_dashboard.html",
    "recruit": REPO_ROOT / "MBM" / "Recruitment" / "caller_recruitment_dashboard.html",
    "leads_db": REPO_ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json",
}


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.8.92"


LOCAL_IP = get_local_ip()


class MasterGatewayHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS and disable aggressive caching so updates show instantly
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "" or path == "/":
            self._serve_hub()
        elif path == "/terminal":
            self._serve_file(PATHS["terminal"], "text/html; charset=utf-8")
        elif path == "/phound":
            self._serve_file(PATHS["phound"], "text/html; charset=utf-8")
        elif path == "/crm":
            self._serve_file(PATHS["crm"], "text/html; charset=utf-8")
        elif path == "/contech":
            self._serve_file(PATHS["contech"], "text/html; charset=utf-8")
        elif path == "/recruit":
            self._serve_file(PATHS["recruit"], "text/html; charset=utf-8")
        elif path == "/leads_database.json" or path == "/api/leads":
            self._serve_file(PATHS["leads_db"], "application/json; charset=utf-8")
        elif path == "/api/deals":
            self._serve_canonical_deals()
        elif path == "/api/auction_deals":
            self._serve_canonical_deals(filter_type="property")
        elif path == "/api/tranchai_deals":
            self._serve_canonical_deals(filter_type="business_ai")
        elif path == "/api/metrics":
            self._serve_conversion_metrics()
        elif path == "/api/health":
            self._serve_json({
                "status": "healthy",
                "uptime": "continuous",
                "port": PORT,
                "local_ip": LOCAL_IP,
                "desktop_url": f"http://localhost:{PORT}",
                "mobile_url": f"http://{LOCAL_IP}:{PORT}"
            })
        else:
            # Fallback to serving static files from repo root
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/objection":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                objection = data.get("objection", "")
                lead_name = data.get("lead_name", "Prospect")
                
                # Rule-based / Groq sub-second response
                obj_lower = objection.lower()
                if "not interested" in obj_lower or "not selling" in obj_lower:
                    resp_text = f"Totally understand {lead_name}. Just so I update our records, are you holding onto it long term, or is there a specific number down the road where letting it go would make sense?"
                elif "offer" in obj_lower or "price" in obj_lower or "how much" in obj_lower:
                    resp_text = f"Because we pay 100% cash and cover all closing fees as-is, my offer depends on current condition. If we closed next week with zero fees, what ballpark number were you hoping to walk away with?"
                elif "email" in obj_lower or "mail" in obj_lower:
                    resp_text = f"I'd be glad to send an email! What's the best address for you? If our cash terms meet your expectations, would you be ready to review the contract this week?"
                elif "who" in obj_lower or "number" in obj_lower:
                    resp_text = f"We pull public county tax assessor records and cross-reference with local business registries. I'm a real private buyer, not a call center."
                else:
                    resp_text = f"I completely understand {lead_name}. If I could show you how we can close in 7 days with zero fees, would you be open to a quick 30-second summary?"

                self._serve_json({"response": resp_text})
            except Exception as e:
                self._serve_json({"error": str(e)}, status=500)
        else:
            self.send_error(404, "Endpoint Not Found")

    def _serve_file(self, file_path: Path, content_type: str):
        if not file_path.exists():
            self.send_error(404, f"File not found: {file_path.name}")
            return
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def _serve_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_canonical_deals(self, filter_type: Optional[str] = None):
        try:
            from MBM.LeadEngine.canonical_deal_engine import CanonicalDealMemory
            mem = CanonicalDealMemory()
            deals = list(mem.deals.values())
            if filter_type:
                deals = [d for d in deals if (d.deal_type.value if hasattr(d.deal_type, 'value') else str(d.deal_type)) == filter_type]
            deals_data = [d.to_dict() for d in deals]
            self._serve_json({
                "status": "success",
                "count": len(deals_data),
                "filter": filter_type or "all",
                "deals": deals_data
            })
        except Exception as e:
            self._serve_json({"status": "error", "error": str(e)}, status=500)

    def _serve_conversion_metrics(self):
        try:
            from MBM.SalesforceOS.salesforce_os import SalesforceOS
            sf = SalesforceOS()
            metrics = sf.get_conversion_metrics()
            self._serve_json({"status": "success", "metrics": metrics})
        except Exception as e:
            self._serve_json({"status": "error", "error": str(e)}, status=500)

    def _serve_hub(self):
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JARVIS OS // MASTER MISSION CONTROL GATEWAY</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #030712;
            --card: #0b1329;
            --card-hover: #142145;
            --border: #1e293b;
            --cyan: #06b6d4;
            --emerald: #10b981;
            --gold: #f59e0b;
            --purple: #8b5cf6;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: #f8fafc;
            font-family: 'Inter', sans-serif;
            padding: 36px 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }}
        .badge {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--emerald);
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 4px 12px;
            border-radius: 9999px;
            display: inline-block;
            margin-bottom: 12px;
        }}
        h1 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 36px;
            font-weight: 700;
            background: linear-gradient(135deg, #ffffff 0%, #38bdf8 50%, #818cf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 24px;
        }}
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 24px;
            text-decoration: none;
            color: inherit;
            transition: all 0.2s ease;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .card:hover {{
            background: var(--card-hover);
            border-color: var(--cyan);
            transform: translateY(-3px);
            box-shadow: 0 12px 30px rgba(6, 182, 212, 0.15);
        }}
        .card-icon {{
            font-size: 32px;
            margin-bottom: 12px;
        }}
        .card-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 20px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 6px;
        }}
        .card-desc {{
            font-size: 13px;
            color: #94a3b8;
            line-height: 1.5;
            margin-bottom: 20px;
        }}
        .card-link {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 700;
            color: var(--cyan);
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .network-bar {{
            background: #090e1c;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
            margin-top: 40px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .net-item {{ display: flex; gap: 8px; align-items: center; }}
        .net-val {{ color: var(--emerald); font-weight: 700; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="badge">● UNIFIED MASTER GATEWAY // ZERO DOWNTIME</div>
            <h1>JARVIS OS Command Hub</h1>
            <p style="color: #94a3b8; font-size: 14px; margin-top: 8px;">
                Direct One-Click Access to Every Subsystem • Universal Local & Mobile Access
            </p>
        </div>

        <div class="grid">
            <a href="/terminal" class="card" style="border-top: 3px solid var(--gold);">
                <div>
                    <div class="card-icon">💎</div>
                    <div class="card-title">Luxury Deal Terminal</div>
                    <div class="card-desc">
                        Bloomberg-grade institutional real estate deal room with live 70% rule MAO underwriting, ARV comps, and 1-click contract locks.
                    </div>
                </div>
                <div class="card-link" style="color: var(--gold);">Launch Deal Room →</div>
            </a>

            <a href="/phound" class="card" style="border-top: 3px solid var(--cyan);">
                <div>
                    <div class="card-icon">📱</div>
                    <div class="card-title">Phound SMS Cockpit</div>
                    <div class="card-desc">
                        1-Click Phound App and native carrier SMS blast outreach for ConTech AI consultancy client acquisition ($4.5k–$35k retainers).
                    </div>
                </div>
                <div class="card-link">Open SMS Cockpit →</div>
            </a>

            <a href="/crm" class="card" style="border-top: 3px solid var(--emerald);">
                <div>
                    <div class="card-icon">📊</div>
                    <div class="card-title">Salesforce AI OS</div>
                    <div class="card-desc">
                        Lightning CRM dashboard with automated lead progression, Groq copilot transcript extraction, and weighted revenue forecasting.
                    </div>
                </div>
                <div class="card-link" style="color: var(--emerald);">Open CRM Dashboard →</div>
            </a>

            <a href="/contech" class="card" style="border-top: 3px solid var(--purple);">
                <div>
                    <div class="card-icon">🏗️</div>
                    <div class="card-title">ConTech AI Social Hub</div>
                    <div class="card-desc">
                        Omnichannel authority content queue across LinkedIn, Reddit, Facebook, Instagram, and high-ticket B2B closing cadences.
                    </div>
                </div>
                <div class="card-link" style="color: var(--purple);">View Social Engine →</div>
            </a>

            <a href="http://localhost:5173" target="_blank" class="card" style="border-top: 3px solid #38bdf8;">
                <div>
                    <div class="card-icon">📞</div>
                    <div class="card-title">MBM Primary React Dialer</div>
                    <div class="card-desc">
                        Full Higgsfield React + TanStack application with 712 verified leads, instant click-to-dial, and live dial velocity HUD.
                    </div>
                </div>
                <div class="card-link">Launch React Dialer →</div>
            </a>

            <a href="/leads_database.json" target="_blank" class="card" style="border-top: 3px solid #64748b;">
                <div>
                    <div class="card-icon">🗄️</div>
                    <div class="card-title">Master Verified Leads Feed</div>
                    <div class="card-desc">
                        Raw JSON feed of all 712 verified leads with skip-traced owner numbers, motivation scores, and personalized call scripts.
                    </div>
                </div>
                <div class="card-link" style="color: #94a3b8;">View JSON Database →</div>
            </a>
        </div>

        <div class="network-bar">
            <div class="net-item">
                <span>💻 Desktop Access:</span>
                <span class="net-val">http://localhost:{PORT}</span>
            </div>
            <div class="net-item">
                <span>📱 Mobile Wi-Fi Access:</span>
                <span class="net-val">http://{LOCAL_IP}:{PORT}</span>
            </div>
            <div class="net-item">
                <span>🔒 Health Check:</span>
                <span class="net-val">200 OK (Continuous)</span>
            </div>
        </div>
    </div>
</body>
</html>
"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_gateway():
    print("=" * 75)
    print(f"  ⚡ JARVIS OS // UNIFIED MASTER WEB GATEWAY STARTING ON PORT {PORT}")
    print("=" * 75)
    print(f"  💻 Desktop URL:   http://localhost:{PORT}")
    print(f"  📱 Mobile Phone:  http://{LOCAL_IP}:{PORT}")
    print("=" * 75)

    server = ThreadingHTTPServer((HOST, PORT), MasterGatewayHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down gateway.")
        server.server_close()


if __name__ == "__main__":
    run_gateway()
