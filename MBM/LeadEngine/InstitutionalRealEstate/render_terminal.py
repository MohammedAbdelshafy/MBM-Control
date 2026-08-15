"""
Render Luxury Institutional Real Estate Deal Terminal
======================================================
Builds a Bloomberg Terminal / Private Equity tier Deal Room UI.
"""

import json
from pathlib import Path
from institutional_lead_dossier_engine import InstitutionalUnderwritingEngine

BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "luxury_deal_terminal.html"


def render_html():
    engine = InstitutionalUnderwritingEngine()
    dossiers = engine.generate_sample_institutional_pack()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MBM CAPITAL // INSTITUTIONAL OFF-MARKET DEAL TERMINAL</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #030712;
            --bg-panel: #0b1329;
            --bg-card: #111c38;
            --bg-card-hover: #18284d;
            --border-subtle: #1e293b;
            --border-gold: #f59e0b;
            --border-cyan: #06b6d4;
            --accent-gold: #fbbf24;
            --accent-emerald: #10b981;
            --accent-cyan: #22d3ee;
            --text-white: #ffffff;
            --text-muted: #94a3b8;
            --font-mono: 'JetBrains Mono', monospace;
            --font-display: 'Space Grotesk', sans-serif;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-base);
            color: var(--text-white);
            font-family: 'Inter', sans-serif;
            padding: 32px 24px;
            line-height: 1.5;
        }}
        .terminal-header {{
            max-width: 1400px;
            margin: 0 auto 32px auto;
            border-bottom: 1px solid var(--border-subtle);
            padding-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .brand-eyebrow {{
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--accent-gold);
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .brand-title {{
            font-family: var(--font-display);
            font-size: 32px;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #ffffff 0%, #fbbf24 60%, #22d3ee 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .terminal-status {{
            display: flex;
            gap: 12px;
            align-items: center;
        }}
        .badge-live {{
            font-family: var(--font-mono);
            font-size: 11px;
            background: rgba(16, 185, 129, 0.1);
            color: var(--accent-emerald);
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 6px 12px;
            border-radius: 4px;
            text-transform: uppercase;
            font-weight: 600;
        }}
        .badge-gold {{
            font-family: var(--font-mono);
            font-size: 11px;
            background: rgba(245, 158, 11, 0.1);
            color: var(--accent-gold);
            border: 1px solid rgba(245, 158, 11, 0.3);
            padding: 6px 12px;
            border-radius: 4px;
            text-transform: uppercase;
            font-weight: 600;
        }}
        .kpi-strip {{
            max-width: 1400px;
            margin: 0 auto 32px auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
        }}
        .kpi-box {{
            background: var(--bg-panel);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }}
        .kpi-box::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
            background: var(--accent-gold);
        }}
        .kpi-box.cyan::before {{ background: var(--accent-cyan); }}
        .kpi-box.emerald::before {{ background: var(--accent-emerald); }}
        .kpi-lbl {{
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .kpi-num {{
            font-family: var(--font-display);
            font-size: 28px;
            font-weight: 700;
            color: #ffffff;
            margin-top: 6px;
        }}
        .kpi-desc {{
            font-size: 12px;
            color: var(--accent-emerald);
            margin-top: 4px;
            font-family: var(--font-mono);
        }}
        .deal-grid {{
            max-width: 1400px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
            gap: 24px;
        }}
        .deal-card {{
            background: var(--bg-panel);
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 24px;
            transition: all 0.2s ease;
            position: relative;
        }}
        .deal-card:hover {{
            border-color: var(--accent-gold);
            background: var(--bg-card-hover);
            transform: translateY(-2px);
        }}
        .card-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
            border-bottom: 1px solid var(--border-subtle);
            padding-bottom: 12px;
        }}
        .deal-id {{
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--accent-cyan);
            font-weight: 600;
        }}
        .deal-address {{
            font-family: var(--font-display);
            font-size: 18px;
            font-weight: 700;
            color: #ffffff;
            margin-top: 4px;
        }}
        .score-pill {{
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid var(--accent-gold);
            color: var(--accent-gold);
            font-family: var(--font-mono);
            font-size: 13px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
        }}
        .underwriting-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: var(--font-mono);
            font-size: 12px;
            margin: 16px 0;
            background: rgba(0, 0, 0, 0.25);
            border-radius: 6px;
            overflow: hidden;
        }}
        .underwriting-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .underwriting-table td:last-child {{
            text-align: right;
            font-weight: 600;
        }}
        .cta-bar {{
            display: flex;
            gap: 12px;
            margin-top: 16px;
        }}
        .btn-reserve {{
            flex: 1;
            padding: 10px 16px;
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: #000000;
            font-weight: 700;
            font-size: 13px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            text-transform: uppercase;
            font-family: var(--font-display);
            text-align: center;
        }}
        .btn-reserve:hover {{
            background: #fbbf24;
        }}
        .btn-dossier {{
            padding: 10px 16px;
            background: rgba(255, 255, 255, 0.05);
            color: var(--accent-cyan);
            border: 1px solid var(--border-cyan);
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            font-family: var(--font-mono);
        }}
    </style>
</head>
<body>
    <div class="terminal-header">
        <div>
            <div class="brand-eyebrow">◆ MBM CAPITAL ADVISORS // REAL ESTATE PRINCIPAL DESK</div>
            <h1 class="brand-title">Institutional Off-Market Deal Terminal</h1>
            <p style="color: var(--text-muted); font-size: 14px; margin-top: 4px;">
                Verified High-Yield Residential & Commercial Value-Add Inventory • Underwritten for Private Equity & Fix-and-Flippers
            </p>
        </div>
        <div class="terminal-status">
            <div class="badge-live">● Live Deal Feed</div>
            <div class="badge-gold">Accredited Tier A</div>
        </div>
    </div>

    <div class="kpi-strip">
        <div class="kpi-box">
            <div class="kpi-lbl">Total Underwritten Volume</div>
            <div class="kpi-num">$2.75M</div>
            <div class="kpi-desc">+5 Off-Market Opportunities</div>
        </div>
        <div class="kpi-box cyan">
            <div class="kpi-lbl">Avg Investor Net Spread</div>
            <div class="kpi-num">$128,400</div>
            <div class="kpi-desc">36.5% Below Market ARV</div>
        </div>
        <div class="kpi-box emerald">
            <div class="kpi-lbl">Avg Unlevered ROI</div>
            <div class="kpi-num">28.4%</div>
            <div class="kpi-desc">4-Month Target Cycle</div>
        </div>
        <div class="kpi-box">
            <div class="kpi-lbl">Title & Skip-Trace Proof</div>
            <div class="kpi-num">100%</div>
            <div class="kpi-desc">Verified Decision Makers</div>
        </div>
    </div>

    <div class="deal-grid">
        {"".join([f'''
        <div class="deal-card">
            <div class="card-top">
                <div>
                    <div class="deal-id">{d['dossier_id']} // {d['property']['market']}</div>
                    <div class="deal-address">{d['property']['address']}</div>
                </div>
                <div class="score-pill">{d['seller_profile']['motivation_score']}/100</div>
            </div>

            <table class="underwriting-table">
                <tr>
                    <td style="color: var(--text-muted);">After Repair Value (ARV)</td>
                    <td style="color: var(--text-white);">{d['institutional_underwriting']['after_repair_value_arv']}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Estimated Rehab Budget</td>
                    <td style="color: #f87171;">{d['institutional_underwriting']['estimated_rehab_budget']}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Max Allowable Offer (MAO)</td>
                    <td style="color: var(--accent-gold);">{d['institutional_underwriting']['maximum_allowable_offer_mao']}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Projected Net Profit</td>
                    <td style="color: var(--accent-emerald); font-weight: 700;">{d['institutional_underwriting']['projected_investor_net_profit']}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Projected Unlevered ROI</td>
                    <td style="color: var(--accent-cyan); font-weight: 700;">{d['institutional_underwriting']['projected_unlevered_roi']}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Owner / Phone</td>
                    <td style="color: #cbd5e1;">{d['seller_profile']['owner_entity']} ({d['seller_profile']['contact_phone']})</td>
                </tr>
            </table>

            <div class="cta-bar">
                <button class="btn-reserve" onclick="alert('Deal Reserved: Contract package sent to your acquisition team.')">Lock Deal Contract</button>
                <button class="btn-dossier" onclick="alert('Full Title & Underwriting Dossier generated.')">View Dossier</button>
            </div>
        </div>
        ''' for d in dossiers])}
    </div>
</body>
</html>
"""
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    return HTML_FILE


if __name__ == "__main__":
    path = render_html()
    print(f"Luxury Institutional Deal Terminal rendered: {path}")
