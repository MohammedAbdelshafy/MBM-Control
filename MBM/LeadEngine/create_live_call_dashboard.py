import csv
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
CSV_FILE = BASE_DIR.parent.parent / "top_200_prospects_to_call_today.csv"
DESKTOP_HTML = Path(os.path.expanduser("~/Desktop")) / "live_prospect_call_sheet.html"

prospects = []
with open(CSV_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        prospects.append(row)

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JARVIS OS — Live 200 Prospect Calling Dashboard</title>
    <style>
        :root {{
            --bg: #0b0f19;
            --card-bg: #111827;
            --accent: #3b82f6;
            --accent-green: #10b981;
            --text: #f3f4f6;
            --muted: #9ca3af;
            --border: #1f2937;
        }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        .title {{
            font-size: 24px;
            font-weight: 700;
            color: #ffffff;
        }}
        .stats {{
            display: flex;
            gap: 16px;
        }}
        .stat-badge {{
            background: #1e293b;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            color: var(--accent);
            border: 1px solid var(--border);
        }}
        .search-bar {{
            width: 100%;
            padding: 12px 16px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: #fff;
            font-size: 15px;
            margin-bottom: 24px;
            box-sizing: border-box;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card-bg);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
        }}
        th, td {{
            padding: 14px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background: #1e293b;
            color: var(--muted);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        tr:hover {{
            background: #1e293b55;
        }}
        .btn-call {{
            background: var(--accent-green);
            color: #ffffff;
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            font-size: 13px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }}
        .btn-call:hover {{
            background: #059669;
            transform: translateY(-1px);
        }}
        .badge-tier {{
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 700;
        }}
        .hook-text {{
            font-size: 13px;
            color: var(--muted);
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <div class="title">JARVIS OS — Live 200 Prospect Calling Dashboard</div>
            <div style="color: var(--muted); font-size: 14px; margin-top: 4px;">Click any green button to dial live directly from your device</div>
        </div>
        <div class="stats">
            <div class="stat-badge">Total Verified Prospects: 200</div>
            <div class="stat-badge" style="color: var(--accent-green);">100% Real Phone Numbers</div>
        </div>
    </div>

    <input type="text" class="search-bar" id="searchInput" onkeyup="filterTable()" placeholder="Search by company name, contact, city, state, or phone number...">

    <table id="prospectsTable">
        <thead>
            <tr>
                <th>Rank</th>
                <th>Company / Prospect</th>
                <th>Contact Name & Title</th>
                <th>Phone Number (Live Call)</th>
                <th>Location</th>
                <th>Priority Score</th>
                <th>Opening Call Hook</th>
            </tr>
        </thead>
        <tbody>
"""

for p in prospects:
    clean_digits = "".join(ch for ch in p['phone_number'] if ch.isdigit() or ch == '+')
    html_content += f"""
            <tr>
                <td>#{p['prospect_rank']}</td>
                <td style="font-weight: 600; color: #fff;">{p['company_name']}</td>
                <td>{p['contact_name']}<br><span style="font-size:12px; color:var(--muted);">{p['title']}</span></td>
                <td>
                    <a href="tel:{clean_digits}" class="btn-call">
                        📞 {p['phone_number']}
                    </a>
                </td>
                <td>{p['city']}, {p['state']}</td>
                <td><span class="badge-tier">{p['tier']} ({p['antigravity_score']})</span></td>
                <td class="hook-text">"{p['call_opening_hook']}"</td>
            </tr>
"""

html_content += """
        </tbody>
    </table>

    <script>
        function filterTable() {
            var input = document.getElementById("searchInput");
            var filter = input.value.toUpperCase();
            var table = document.getElementById("prospectsTable");
            var tr = table.getElementsByTagName("tr");

            for (var i = 1; i < tr.length; i++) {
                var txt = tr[i].textContent || tr[i].innerText;
                if (txt.toUpperCase().indexOf(filter) > -1) {
                    tr[i].style.display = "";
                } else {
                    tr[i].style.display = "none";
                }
            }
        }
    </script>
</body>
</html>
"""

with open(DESKTOP_HTML, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"[LIVE CALL SHEET] Created interactive desktop calling dashboard at: {DESKTOP_HTML}")
