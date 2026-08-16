# 🌐 MBM Ecosystem — GLM Repository & Subsystem Inventory
**Generated:** 2026-08-16 22:37:01  
**Total Tracked Repositories / Subsystems:** 7  

---

## 📊 Executive Subsystem Matrix

| Subsystem / Repository | Path | Git Branch | Tech Stack | Risk Level | Revenue Role |
|---|---|---|---|---|---|
| **Base44 Control Plane (Root Monorepo)** | `.` | `master` | React 18 | `CRITICAL` | Core Operating Platform, GTM Engine, Monorepo Orchestration |
| **MBM Dialer (Tonight Caller Cockpit)** | `mbm-dialer` | `main` | TanStack Start / Router | `CRITICAL` | Primary Calling & Closing Interface (Sellers + AI Consultancy) |
| **MBM-Social (Multi-Brand Media & Content OS)** | `MBM-Social` | `master` | Python 3.11 | `HIGH` | Top-of-Funnel Content Ingestion, Engagement & Business Signal Discovery |
| **MBM LeadEngine (GTM Intelligence & Discovery)** | `MBM/LeadEngine` | `master` | Python 3.11 | `CRITICAL` | 100+ Daily Fresh Verified Leads, GTM Attribution, Discovery, Meeting Booking |
| **Clipping Factory (Autonomous Video Engine)** | `clipping-factory` | `master` | Python / FastAPI | `MEDIUM` | Automated Short-Form & Video Asset Production Engine |
| **MBM Ops & Real Estate Underwriting** | `MBM` | `master` | Python 3.11 | `HIGH` | Wholesale Deal Assignment, Property Dossiers, Cash Offer Underwriting |
| **ConTech BOQ & CAD Estimator Subsystem** | `MBM-Social/ContechAI` | `master` | Python 3.11 | `MEDIUM` | High-Ticket Construction AI Retainers & CAD-to-BOQ Automation ($2,497/mo) |

---

## 🔍 Detailed Subsystem Dossiers

### 📦 Base44 Control Plane (Root Monorepo)
- **Path:** `.` (`C:\Users\omare\OneDrive\Desktop\AI`)
- **Is Git Repo:** `Yes`
- **Branch:** `master`
- **Latest Commit:** `bb6b294 feat(dialer): finalize tonight seller and AI consultancy calling cockpit`
- **Tech Stack:** React 18 + Vite 6 + Tailwind CSS + FastAPI + Node/Express + Celery + Python 3.11
- **Entrypoints:**
  - `src/main.jsx`
  - `server/index.js`
  - `MBM/LeadEngine/gemini_agent_api.py`
  - `clipping-factory/main.py`
- **Test Suite:** pytest MBM/LeadEngine/tests/ -v (204 tests passing), npm run test
- **Deployment:** Vite dev (:5173), Express (:3002), FastAPI (:3005), Docker Compose stack
- **Dependencies:** package.json (React/Vite), requirements.txt, pyproject.toml
- **Known Blockers:** Auction.com scrape blocked by Incapsula; RapidAPI 429 rate limit observed
- **Revenue Role:** Core Operating Platform, GTM Engine, Monorepo Orchestration
- **Risk Level:** `CRITICAL`
- **Dirty Files Count:** 5124

  **Recent Commits:**
  - `bb6b294 feat(dialer): finalize tonight seller and AI consultancy calling cockpit`
  - `a7ed5f0 feat(gtm): finalize executive money and progress brief for Telegram notification bus`
  - `3485b71 feat(gtm): connect and verify GmailDeliveryAdapter with SMTP transport, IMAP reply detection, and idempotency ledger`
  - `d810566 test(gtm): ensure bus_env fixture isolates from ambient telegram token`
  - `612d759 fix(gtm): align QuickBrief state collection and rendering with hermetic test suite`

---

### 📦 MBM Dialer (Tonight Caller Cockpit)
- **Path:** `mbm-dialer` (`C:\Users\omare\OneDrive\Desktop\AI\mbm-dialer`)
- **Is Git Repo:** `Yes`
- **Branch:** `main`
- **Latest Commit:** `3a5de41 feat(dialer): finalize tonight seller and AI consultancy calling cockpit`
- **Tech Stack:** TanStack Start / Router + React 18 + Tailwind CSS + Bun / Vite
- **Entrypoints:**
  - `mbm-dialer/app/src/routes/index.tsx`
  - `mbm-dialer/app/src/components/dialer/MasterScript.tsx`
  - `mbm-dialer/app/src/router.tsx`
- **Test Suite:** tsc --noEmit (0 errors), bun run build
- **Deployment:** Bun/Vite runtime (:5173), Proxy to FastAPI (:3005)
- **Dependencies:** mbm-dialer/app/package.json (@tanstack/react-router, tailwindcss)
- **Known Blockers:** Historical 762 -> 702 data rewrite race (Resolved with Single-Writer Lock rule)
- **Revenue Role:** Primary Calling & Closing Interface (Sellers + AI Consultancy)
- **Risk Level:** `CRITICAL`
- **Dirty Files Count:** 0

  **Recent Commits:**
  - `3a5de41 feat(dialer): finalize tonight seller and AI consultancy calling cockpit`
  - `06762d4 feat(dialer): reconcile 762 dial-ready leads with seller-first Top 100 ordering and preserved recovery records`
  - `d0932f1 feat(dialer): add SpiralBackdrop background component`
  - `2af5209 feat(dialer): sync 762 verified leads, Top 100 priority ordering, Live Dial HUD, and isolated PostCSS build`
  - `7ecc72f Sellers cleanup: drop 62 no-address rows; slot 50 verified SFH with real DCAD offers + scripts`

---

### 📦 MBM-Social (Multi-Brand Media & Content OS)
- **Path:** `MBM-Social` (`C:\Users\omare\OneDrive\Desktop\AI\MBM-Social`)
- **Is Git Repo:** `Yes`
- **Branch:** `master`
- **Latest Commit:** `60742d2 Add oversee command: orchestrator + Telegram + GitHub agents unified`
- **Tech Stack:** Python 3.11 + Pydantic + SQLite + Docker + ComfyUI + Playwright
- **Entrypoints:**
  - `MBM-Social/mbm.py`
  - `MBM-Social/Operations/campaign_runtime.py`
  - `MBM-Social/Operations/oauth_manager.py`
  - `MBM-Social/Factories/PublishFactory/publish_worker.py`
- **Test Suite:** pytest MBM-Social/tests/
- **Deployment:** Docker Compose (ComfyUI + Workers + Telegram Daemon)
- **Dependencies:** MBM-Social/requirements.txt (playwright, yt-dlp, pydantic, groq)
- **Known Blockers:** YouTube OAuth interactive flow requires browser auth on first run
- **Revenue Role:** Top-of-Funnel Content Ingestion, Engagement & Business Signal Discovery
- **Risk Level:** `HIGH`
- **Dirty Files Count:** 95

  **Recent Commits:**
  - `60742d2 Add oversee command: orchestrator + Telegram + GitHub agents unified`
  - `84e6bf4 Add live web dashboard + Telegram dashboard to see pipeline progress`
  - `beab433 Fix asyncio.Lock -> threading.Lock in health_monitor, pipeline test runs end-to-end`
  - `4e4c2a2 Wire full factory pipeline + GraphOS observer into orchestrator startup`
  - `2cd4906 98/98 pass: fix dequeue dep infinite loop, fix CircuitBreaker stale state, remove all deprecation warnings`

---

### 📦 MBM LeadEngine (GTM Intelligence & Discovery)
- **Path:** `MBM/LeadEngine` (`C:\Users\omare\OneDrive\Desktop\AI\MBM\LeadEngine`)
- **Is Git Repo:** `Nested Subsystem`
- **Branch:** `master`
- **Latest Commit:** `Tracked in parent`
- **Tech Stack:** Python 3.11 + FastAPI + Pydantic v2 + SQLite + Groq LPU + Gemini 2.5 + NVIDIA NIM
- **Entrypoints:**
  - `MBM/LeadEngine/gemini_agent_api.py`
  - `MBM/LeadEngine/daily_fresh_lead_factory.py`
  - `MBM/LeadEngine/gtm_commander.py`
  - `MBM/LeadEngine/gtm_notification_bus.py`
  - `MBM/LeadEngine/conversation_engine.py`
- **Test Suite:** pytest MBM/LeadEngine/tests/ -v (204 tests passing)
- **Deployment:** FastAPI daemon on port 3005, CLI daemons, Scheduled Cron
- **Dependencies:** requirements.txt (fastapi, uvicorn, groq, google-genai)
- **Known Blockers:** Twilio Lookup 401 (Replaced by Free CMS NPI & DCAD Verified records)
- **Revenue Role:** 100+ Daily Fresh Verified Leads, GTM Attribution, Discovery, Meeting Booking
- **Risk Level:** `CRITICAL`
- **Dirty Files Count:** 0

---

### 📦 Clipping Factory (Autonomous Video Engine)
- **Path:** `clipping-factory` (`C:\Users\omare\OneDrive\Desktop\AI\clipping-factory`)
- **Is Git Repo:** `Nested Subsystem`
- **Branch:** `master`
- **Latest Commit:** `Tracked in parent`
- **Tech Stack:** Python / FastAPI + Celery + Redis + Docker + PostgreSQL + MinIO
- **Entrypoints:**
  - `clipping-factory/main.py`
  - `clipping-factory/tasks.py`
  - `clipping-factory/worker.py`
- **Test Suite:** pytest clipping-factory/tests/
- **Deployment:** 12-Container Docker Compose Stack (API, workers, beat, Redis, MinIO)
- **Dependencies:** clipping-factory/requirements.txt, Dockerfile
- **Known Blockers:** Local GPU rendering requires CUDA/NVIDIA container toolkit
- **Revenue Role:** Automated Short-Form & Video Asset Production Engine
- **Risk Level:** `MEDIUM`
- **Dirty Files Count:** 0

---

### 📦 MBM Ops & Real Estate Underwriting
- **Path:** `MBM` (`C:\Users\omare\OneDrive\Desktop\AI\MBM`)
- **Is Git Repo:** `Nested Subsystem`
- **Branch:** `master`
- **Latest Commit:** `Tracked in parent`
- **Tech Stack:** Python 3.11 + RapidAPI + Neteller API + Pandas
- **Entrypoints:**
  - `MBM/LeadEngine/property_intel/ownership_verifier.py`
  - `MBM/LeadEngine/seller_skip_tracer.py`
  - `MBM/Scripts/neteller_config.py`
- **Test Suite:** pytest MBM/LeadEngine/tests/test_property_intel.py
- **Deployment:** Python CLI scripts, Scheduled cron workflows
- **Dependencies:** Python standard library + requests + beautifulsoup4
- **Known Blockers:** County ArcGIS endpoints can have variable latency
- **Revenue Role:** Wholesale Deal Assignment, Property Dossiers, Cash Offer Underwriting
- **Risk Level:** `HIGH`
- **Dirty Files Count:** 0

---

### 📦 ConTech BOQ & CAD Estimator Subsystem
- **Path:** `MBM-Social/ContechAI` (`C:\Users\omare\OneDrive\Desktop\AI\MBM-Social\ContechAI`)
- **Is Git Repo:** `Nested Subsystem`
- **Branch:** `master`
- **Latest Commit:** `Tracked in parent`
- **Tech Stack:** Python 3.11 + DXF parser + Eurocode / MasterFormat Cost Matrix
- **Entrypoints:**
  - `MBM-Social/ContechAI/boq_engine.py`
  - `MBM-Social/ContechAI/cad_parser.py`
- **Test Suite:** pytest MBM-Social/tests/test_contech.py
- **Deployment:** CLI tool & FastAPI endpoint
- **Dependencies:** ezdxf, numpy, pydantic
- **Known Blockers:** Scanned PDF takeoffs require vectorization OCR
- **Revenue Role:** High-Ticket Construction AI Retainers & CAD-to-BOQ Automation ($2,497/mo)
- **Risk Level:** `MEDIUM`
- **Dirty Files Count:** 0

---
