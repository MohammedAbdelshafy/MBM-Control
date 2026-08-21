# 🎯 MBM Dialer Architecture — Single Source of Truth

> **Decision**: The **Higgsfield-generated MBM Dialer** (`mbm-dialer/app/`) is the **ONE AND ONLY** primary dialer for all operations. All other dialers are secondary products that can be sold or deprecated.

---

## ✅ Primary Dialer (ACTIVE — Use This)

| Property | Value |
|---|---|
| **Name** | MBM Dialer (Higgsfield-generated React + TanStack + Tailwind) |
| **Location** | `mbm-dialer/app/` |
| **Tech Stack** | React 18 + Vite 6 + TanStack Router + Tailwind CSS + Radix UI |
| **Database** | `mbm-dialer/app/public/leads_database.json` |
| **Desktop URL** | `http://localhost:5173` |
| **Phone URL** | `http://192.168.8.92:5173` (same Wi-Fi) |
| **Total Leads** | **712 verified** (434 Clinics + 199 RE Sellers + 49 Multi + 30 Cash Buyers) |
| **Features** | Tap-to-call, AI objection handler, motivation scoring, decision tracking, CSV export, QR phone access, live dial HUD |

### Commands
```bash
npm run dialer                # Start the Higgsfield dialer (primary)
npm run dialer:consolidate    # Pull ALL leads from every queue into Higgsfield
npm run leads:push:re         # Push top 100 RE deals to front of queue
```

---

## 🏪 Secondary Dialers (SELLABLE PRODUCTS — Not for internal use)

### 1. ColdCall Cockpit (`coldcall/dialer/`)
- **What it is**: Standalone Python stdlib HTTP server with SQLite backend
- **Tech**: Pure Python + HTML/JS (no framework), Twilio bridge calling
- **Database**: `coldcall/data/coldcall.db` (SQLite)
- **Status**: Available for sale as a standalone product
- **Command**: `npm run dialer:coldcall` (port 8878)

### 2. Luxury Institutional Deal Terminal
- **What it is**: Bloomberg-tier static HTML deal room for institutional buyers
- **Tech**: Single-file HTML with Space Grotesk + JetBrains Mono typography
- **Purpose**: Sales tool to show VIP cash buyers & hedge funds our deal inventory
- **Command**: `npm run luxury:terminal`

---

## 🔄 Data Flow Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│ CMS NPI Registry    │     │ County Skip-Trace     │     │ Facebook Cash      │
│ (434 Clinic Leads)  │     │ (199 RE Sellers)      │     │ Buyers (30)        │
└─────────┬───────────┘     └──────────┬────────────┘     └────────┬───────────┘
          │                            │                           │
          ▼                            ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    consolidate_to_higgsfield_dialer.py                      │
│              (Deduplicates by phone, merges best scripts)                   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    enrich_higgsfield_dialer.py                              │
│     (Cross-pollinates motivation scores, upgraded scripts, tier badges)     │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│            mbm-dialer/app/public/leads_database.json                        │
│                    ★ SINGLE SOURCE OF TRUTH ★                               │
│                    712 Verified Dial-Ready Leads                             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 Higgsfield MBM Dialer React App                             │
│               http://localhost:5173 (Desktop)                               │
│               http://192.168.8.92:5173 (Phone)                              │
│                                                                             │
│  Features:                                                                  │
│  • Tap-to-call with tel: links                                              │
│  • AI Objection Handler (Groq LLM backend)                                  │
│  • Live Dial HUD (velocity/hr, dials today, hot leads)                      │
│  • Decision tracking (Deal/Nurture/Dead + follow-up scheduling)             │
│  • Motivation tier badges (VERY_HIGH → LOW)                                 │
│  • Quality filter (All / Verified / Enriched)                               │
│  • CSV export of all decisions                                              │
│  • QR code for instant phone access                                         │
│  • Spiral backdrop animation                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```
