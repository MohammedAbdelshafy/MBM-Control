import csv
import os
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARTIFACTS = BASE.parent / "Artifacts"
CALLSHEET = ARTIFACTS / "npi_verified_callsheet.csv"

def load_leads(limit=10):
    if not CALLSHEET.exists():
        return []
    with open(CALLSHEET, encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: (int(r.get("priority", 9)), r.get("phone", "")))
    return rows[:limit]

def generate_dashboard():
    leads = load_leads(10)
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MBM Master Dialer Dashboard</title>
        <style>
            body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
            .container { max-width: 900px; margin: 0 auto; }
            h1 { text-align: center; color: #38bdf8; }
            .lead-card { background-color: #1e293b; border-radius: 12px; padding: 25px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border: 1px solid #334155; }
            .header-flex { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #334155; padding-bottom: 15px; }
            .contact-info h2 { margin: 0; color: #f1f5f9; font-size: 24px; }
            .contact-info p { margin: 5px 0 0 0; color: #94a3b8; font-size: 16px; }
            .dial-btn { display: inline-block; background-color: #10b981; color: white; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 18px; transition: background 0.2s; }
            .dial-btn:hover { background-color: #059669; }
            .script-box { background-color: #0f172a; border-left: 4px solid #38bdf8; padding: 15px; margin-top: 20px; font-size: 16px; line-height: 1.6; border-radius: 0 8px 8px 0; }
            .script-section { font-weight: bold; color: #38bdf8; margin-top: 15px; }
            .highlight { color: #fcd34d; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔥 MBM Master Dialer Dashboard 🔥</h1>
            <p style="text-align:center; color:#94a3b8; margin-bottom:40px;">Click the green CALL button to instantly push the number to Phound.</p>
    """
    
    for i, r in enumerate(leads, 1):
        company = r.get('company_name', 'your practice').title()
        contact = r.get('authorized_official_name', 'Doctor').title()
        vertical = r.get('vertical_tag', 'medical practice').upper()
        phone = r.get('phone', '')
        
        html += f"""
        <div class="lead-card">
            <div class="header-flex">
                <div class="contact-info">
                    <h2>{i}. {contact}</h2>
                    <p>🏥 {company} &nbsp;|&nbsp; 💉 {vertical} &nbsp;|&nbsp; 📞 {phone}</p>
                </div>
                <a href="tel:{phone}" class="dial-btn">📞 CALL NOW</a>
            </div>
            
            <div class="script-box">
                <div class="script-section">[1. THE PATTERN INTERRUPT]</div>
                "Hey <span class="highlight">{contact}</span>, this is Mohammed. I know I'm catching you entirely off guard right now... do you have 30 seconds for me to tell you why I called, and you can hang up if you hate it?"
                
                <div class="script-section">[2. THE HOOK]</div>
                "I run a patient-acquisition engine specifically for <span class="highlight">{vertical}</span> clinics in your area. I have a list of verified local patients looking for treatment, but my current partner clinic is fully booked. Are you currently taking on new patients at <span class="highlight">{company}</span>?"
                
                <div class="script-section">[3. THE QUALIFICATION]</div>
                "Perfect. We don't sell marketing. We physically drop pre-qualified, cash-ready patients directly into your schedule, and we handle all the no-show follow-ups."
                
                <div class="script-section">[4. THE CLOSE (RISK REVERSAL)]</div>
                "Our Patient-Growth Retainer is $497, but here's the catch: I don't want you to pay me a single cent until after our first onboarding call, when you physically see the system working. If it doesn't make sense, we walk away. Sound fair enough to just take a look?"
            </div>
        </div>
        """
        
    html += """
        </div>
    </body>
    </html>
    """
    
    out_path = BASE / "logs" / "dialer_dashboard.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    return out_path

if __name__ == "__main__":
    path = generate_dashboard()
    print(f"Generated Dashboard at: {path}")
    webbrowser.open(f"file://{path}")
