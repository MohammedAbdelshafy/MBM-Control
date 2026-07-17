# MBM LeadPoster

Posts MBM real-estate leads (from `MBM/LeadPacks/*.csv`) to a pay-per-lead
marketplace via **manual/form submission** (Playwright + a saved login session).
No API key, no hardcoded credentials.

## Flow
1. `MBM/Scripts/daily_lead_pack.py` (or `free_lead_engine.py`) produces lead CSVs.
2. `poster.py` reads the latest pack and maps each lead to the marketplace form.
3. `export_marketplace_session.py` captures your logged-in seller session once.
4. `poster.py --post` submits each not-yet-posted lead and records it in `posted.json`.

## Commands
```powershell
cd MBM/LeadPoster

# 1) Validate mapping + count (no browser, safe default)
python poster.py

# 2) Capture your marketplace login session (opens a browser; log in, press Enter)
python export_marketplace_session.py realestate_leadmarket

# 3) Actually post (needs the session from step 2)
python poster.py --post

# Options
python poster.py --site <name> --pack 2026-07-07 --post
```

## Adding a marketplace (config only)
Drop `sites/<name>.yaml` with the real `post_url`, `login_url`, `field_map`
(CSV column -> CSS selector), and `submit_selector`/`success_selector`. No code
changes. `poster.py --site <name>` uses it.

## Safety
- **Dry-run by default** — never opens a browser unless `--post` is passed.
- A ledger (`posted.json`) prevents re-posting the same lead.
- Leads are B2B real-estate businesses (wholesalers/buyers), not consumer PII.
- Replace the `realestate_leadmarket.yaml` template's placeholder URL/selectors
  with the real marketplace before posting.
