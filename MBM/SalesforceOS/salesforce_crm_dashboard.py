"""
Salesforce AI OS — Interactive Lightning CRM Dashboard (16 Canonical Stages)
=============================================================================
Renders an executive Salesforce-style Kanban pipeline, Conversion Analytics HUD,
and Multi-Vertical Deal Table directly from Canonical Deal Memory.
"""

from __future__ import annotations

import os
import sys
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.canonical_deal_engine import CanonicalDealMemory, DealStage, DealType
from MBM.SalesforceOS.salesforce_os import SalesforceOS, CANONICAL_STAGES

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DASHBOARD_HTML = BASE_DIR / "salesforce_crm.html"
DB_PATH = DATA_DIR / "salesforce_crm.db"


def render_salesforce_html() -> Path:
    sf = SalesforceOS(DB_PATH)
    sf.sync_from_deal_memory()
    metrics = sf.get_conversion_metrics()
    pipeline = sf.get_kanban_pipeline()

    mem = CanonicalDealMemory()
    deals = list(mem.deals.values())

    total_value_str = f"${metrics['financials']['total_pipeline_value']:,.2f}"
    weighted_val_str = f"${metrics['financials']['weighted_pipeline_value']:,.2f}"
    won_val_str = f"${metrics['financials']['closed_won_revenue']:,.2f}"
    avg_deal_str = f"${metrics['financials']['average_deal_value']:,.2f}"

    rates = metrics["rates"]

    # Active stages to display prominently in Kanban
    display_stages = [
        "NEW", "QUALIFIED", "CONTACTED", "CONNECTED", "DISCOVERY",
        "INTERESTED", "DEMO_BOOKED", "DEMO_COMPLETE", "PROPOSAL",
        "NEGOTIATION", "CLOSED_WON", "FOLLOW_UP"
    ]

    kanban_cols_html = []
    for st in display_stages:
        stage_opps = pipeline.get(st, [])
        cards_html = []
        for o in stage_opps[:8]:  # show up to 8 per column
            amt = float(o.get("amount") or 0)
            prob = o.get("probability", 0)
            deal_name = o.get("name") or "Unnamed Deal"
            vertical = o.get("vertical") or "Real Estate / AI"
            next_act = o.get("next_action") or "Follow Up"
            neteller_url = o.get("neteller_link") or "#"

            cards_html.append(f"""
            <div class="deal-card">
                <div class="deal-title">{deal_name[:32]}</div>
                <div class="deal-vertical">{vertical}</div>
                <div class="deal-meta">
                    <span class="deal-amt">${amt:,.0f}</span>
                    <span class="deal-prob">{prob}% Win</span>
                </div>
                <div class="deal-next">⚡ Next: {next_act[:25]}</div>
                {f'<a href="{neteller_url}" target="_blank" class="neteller-btn">💳 Neteller Link</a>' if neteller_url and neteller_url != '#' else ''}
            </div>
            """)
        kanban_cols_html.append(f"""
        <div class="kanban-col">
            <div class="col-header">
                <span>{st}</span>
                <span class="col-count">{len(stage_opps)}</span>
            </div>
            <div class="cards-container">
                {''.join(cards_html) if cards_html else '<div class="empty-stage">No active deals</div>'}
            </div>
        </div>
        """)

    # Deals Table Rows
    deals_rows_html = []
    for d in deals[:30]:
        val = d.potential_fee or d.calculated_mao or 2500.0
        badge_color = "#38bdf8" if d.deal_type == DealType.PROPERTY else "#a855f7"
        stage_val = d.stage.value if hasattr(d.stage, "value") else str(d.stage)
        status_color = "#4ade80" if stage_val in ("QUALIFIED", "INTERESTED", "CLOSED_WON") else "#94a3b8"

        deals_rows_html.append(f"""
        <tr>
            <td><strong>{d.owner_name or 'Decision Maker'}</strong></td>
            <td>{d.company_name or d.property_address or 'Private Client'}</td>
            <td><span class="badge" style="background: rgba(56, 189, 248, 0.15); color: {badge_color};">{d.vertical}</span></td>
            <td><code>{d.contact_phone or 'Pending'}</code></td>
            <td><span style="color: {status_color}; font-weight: 600;">{stage_val}</span></td>
            <td><strong style="color: #4ade80;">${val:,.0f}</strong></td>
            <td><span style="color: #f59e0b;">{d.deal_score}/100</span></td>
            <td>{d.next_action}</td>
        </tr>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JARVIS OS // Salesforce AI CRM Platform</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --sf-blue: #0176d3;
            --sf-navy: #030712;
            --sf-card: #0b1329;
            --sf-card-hover: #142145;
            --sf-border: #1e293b;
            --sf-accent: #00e5ff;
            --sf-green: #10b981;
            --sf-gold: #f59e0b;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--sf-navy);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            padding: 24px;
            min-height: 100vh;
        }}
        .navbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--sf-border);
            margin-bottom: 24px;
        }}
        .logo {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 22px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
            color: #ffffff;
        }}
        .logo span {{ color: var(--sf-accent); }}
        .nav-tabs {{ display: flex; gap: 12px; }}
        .nav-tab {{
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-sub);
            text-decoration: none;
            transition: all 0.2s;
        }}
        .nav-tab.active {{ background: var(--sf-blue); color: #ffffff; }}
        .kpi-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--sf-card);
            border: 1px solid var(--sf-border);
            border-radius: 10px;
            padding: 18px;
        }}
        .kpi-label {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--text-sub);
            text-transform: uppercase;
            font-weight: 600;
        }}
        .kpi-val {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 24px;
            font-weight: 700;
            color: #ffffff;
            margin-top: 4px;
        }}
        .kpi-sub {{
            font-size: 12px;
            color: var(--sf-green);
            margin-top: 4px;
        }}
        .analytics-bar {{
            background: #090e1c;
            border: 1px solid var(--sf-border);
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 28px;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
        }}
        .an-item span:first-child {{ color: var(--text-sub); }}
        .an-item span:last-child {{ color: var(--sf-accent); font-weight: 700; }}
        .kanban-board {{
            display: flex;
            gap: 14px;
            overflow-x: auto;
            padding-bottom: 20px;
            margin-bottom: 32px;
        }}
        .kanban-col {{
            flex: 0 0 280px;
            background: var(--sf-card);
            border: 1px solid var(--sf-border);
            border-radius: 10px;
            padding: 14px;
            display: flex;
            flex-direction: column;
        }}
        .col-header {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 700;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--sf-border);
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            color: var(--sf-accent);
        }}
        .col-count {{
            background: rgba(0, 229, 255, 0.15);
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 11px;
        }}
        .cards-container {{ display: flex; flex-direction: column; gap: 10px; }}
        .deal-card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--sf-border);
            border-radius: 8px;
            padding: 12px;
            transition: all 0.2s;
        }}
        .deal-card:hover {{
            border-color: var(--sf-blue);
            background: var(--sf-card-hover);
            transform: translateY(-2px);
        }}
        .deal-title {{ font-size: 13px; font-weight: 600; color: #ffffff; }}
        .deal-vertical {{ font-size: 11px; color: var(--text-sub); margin-top: 2px; }}
        .deal-meta {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            display: flex;
            justify-content: space-between;
            margin-top: 8px;
        }}
        .deal-amt {{ color: var(--sf-green); font-weight: 700; }}
        .deal-prob {{ color: var(--sf-gold); }}
        .deal-next {{ font-size: 11px; color: #38bdf8; margin-top: 6px; }}
        .neteller-btn {{
            display: inline-block;
            margin-top: 8px;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
            padding: 4px 8px;
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: #4ade80;
            border-radius: 4px;
            text-decoration: none;
        }}
        .empty-stage {{ font-size: 11px; color: #64748b; text-align: center; padding: 16px 0; }}
        .section-header {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 16px;
            color: #ffffff;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--sf-card);
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid var(--sf-border);
            font-size: 13px;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--sf-border);
        }}
        th {{
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-sub);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
        }}
        .badge {{
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="navbar">
        <div class="logo">⚡ JARVIS <span>Salesforce AI OS</span></div>
        <div class="nav-tabs">
            <a href="/crm" class="nav-tab active">16-Stage Kanban</a>
            <a href="/terminal" class="nav-tab">Deal Terminal</a>
            <a href="/phound" class="nav-tab">SMS Cockpit</a>
            <a href="http://localhost:5173" class="nav-tab">React Dialer</a>
        </div>
    </div>

    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">Total Pipeline Value</div>
            <div class="kpi-val">{total_value_str}</div>
            <div class="kpi-sub">Across All Active Verticals</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Weighted Expected Revenue</div>
            <div class="kpi-val">{weighted_val_str}</div>
            <div class="kpi-sub">Probability Adjusted</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Average Deal Value</div>
            <div class="kpi-val">{avg_deal_str}</div>
            <div class="kpi-sub">Per Qualified Deal</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Active Canonical Deals</div>
            <div class="kpi-val">{len(deals)}</div>
            <div class="kpi-sub">Property & B2B AI Deals</div>
        </div>
    </div>

    <!-- Phase 8 Close Rate & Conversion Analytics -->
    <div class="analytics-bar">
        <div class="an-item"><span>📞 Connect Rate:</span> <span>{rates['connect_rate_pct']}%</span></div>
        <div class="an-item"><span>🎯 Qualified Rate:</span> <span>{rates['qualified_rate_pct']}%</span></div>
        <div class="an-item"><span>💡 Demo Booking Rate:</span> <span>{rates['demo_rate_pct']}%</span></div>
        <div class="an-item"><span>📝 Proposal Rate:</span> <span>{rates['proposal_rate_pct']}%</span></div>
        <div class="an-item"><span>🏆 Close Rate:</span> <span>{rates['close_rate_pct']}%</span></div>
    </div>

    <div class="section-header">
        <span>📊 16-Stage Opportunity Pipeline</span>
        <span style="font-size: 12px; color: var(--text-sub); font-family: 'JetBrains Mono';">Live Deal Memory Sync</span>
    </div>
    <div class="kanban-board">
        {''.join(kanban_cols_html)}
    </div>

    <div class="section-header">
        <span>👥 Unified Deals Register (Top 30)</span>
        <span style="font-size: 12px; color: var(--text-sub); font-family: 'JetBrains Mono';">Strict Provenance • Neteller Linked</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Decision Maker</th>
                <th>Company / Property</th>
                <th>Vertical</th>
                <th>Phone Number</th>
                <th>Deal Stage</th>
                <th>Value</th>
                <th>Score</th>
                <th>Next Action</th>
            </tr>
        </thead>
        <tbody>
            {''.join(deals_rows_html)}
        </tbody>
    </table>
</body>
</html>
"""
    with open(DASHBOARD_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    return DASHBOARD_HTML


if __name__ == "__main__":
    path = render_salesforce_html()
    print(f"Salesforce CRM HTML Dashboard rendered: {path}")
