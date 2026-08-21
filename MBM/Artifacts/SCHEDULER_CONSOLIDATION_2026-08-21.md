# Scheduler Consolidation Ledger — 2026-08-21

Operator: OpenCode (ox-alpha) | Rule: DISABLE ONLY, zero deletions | Rollback: `schtasks /Change /TN "<TASK>" /ENABLE`

## KEPT (4)

| Task | Command | Frequency | Purpose |
|---|---|---|---|
| MBM_Social_PacedPublisher | `.venv\Scripts\python.exe clipping-factory\MBM-Social\paced_cycle.py` | 15 min (45-min cap; pace gate ≤5 posts/day) | A: MBM-Social production cycle (feed queue best-effort + paced publish). Higgsfield not in path. |
| MBM_LeadEngine_4HR | `powershell -File MBM\Scripts\lead_engine_forever.ps1` | 4 h (2-h cap) | D: full lead pipeline (evidence→skip-trace→QA→qualification→packs→matching→scoring→outreach), heartbeat + Telegram. |
| JarvisOS_MasterOnlineRevenueEngine | `powershell -File MBM\Scripts\run_master_online_revenue_workflow.ps1` | 6 h (2-h cap) | Master revenue workflow (bidding, audits, deal matching). Healthy (last result 0). |
| MBM_DailyDigest | `python MBM\Scripts\telegram_notify.py daily_digest` | Daily 09:00 | Telegram 24-h digest — operator visibility. |

## DISABLED

| Task | Status Before | Action | Reason | Replacement |
|---|---|---|---|---|
| JarvisOS_15Min_VideoAgentFactory | Enabled (result 0) | Disabled 2026-08-21 | Legacy duplicate production cycle (`publish_cycle.py`); superseded by `paced_cycle.py` per its own docstring; ran factory+publish concurrently with PacedPublisher → collision. | MBM_Social_PacedPublisher |
| JarvisOS_MultiChannelPublisher | Enabled (0x80070002 every 15 min) | Disabled 2026-08-21 | Action script `start_continuous_youtube_publisher.py` does not exist on disk. Dead task. | MBM_Social_PacedPublisher |
| emails outreach | Enabled (0x800710E0) | Disabled 2026-08-21 | Exact duplicate of MBM_LeadEngine_4HR (same script, daily 12:10). Required UAC elevation to disable. | MBM_LeadEngine_4HR |
| MBM_Watchdog | Enabled (result 1) | Disabled 2026-08-21 | Kills ALL python processes older than 4 h (kills long renders/publishes) and force-starts engine with no single-instance lock → collision generator. | Task Scheduler IgnoreNew + engine internal retries; heartbeat.json still written for manual checks |
| LeadsRunner5Daily | Enabled (result 0) | Disabled 2026-08-21 | MissionControl find-leads agent dispatch redundant with engine pipeline. | MBM_LeadEngine_4HR |
| LeadsDailyCycle | Enabled (result 0) | Disabled 2026-08-21 | MissionControl executor+packs duplicates engine Steps 8+11; cmd contains hardcoded OpenRouter key (rotate!). | MBM_LeadEngine_4HR |
| MBM_DailyLeadPack | Enabled (result 0) | Disabled 2026-08-21 | `daily_lead_pack.py` already runs as engine Step 8. | MBM_LeadEngine_4HR Step 8 |
| MBM-HUNTER-Daily | Enabled (-196608) | Disabled 2026-08-21 | Action script `run_hunter_daily.ps1` does not exist. Dead task. Outreach covered by engine Steps 11–12. | MBM_LeadEngine_4HR |
| JarvisOS_DataVaultBackup | Enabled (0x800710E0 on battery) | Disabled 2026-08-21 | Workspace lives in OneDrive (continuous cloud copy); task refused to run on battery anyway. | OneDrive sync + manual `python MBM/DataVault/data_vault_backup.py` before risky ops |
| JarvisOS_DatabaseAndLogsCleanup | Enabled (0xC000013A) | Disabled 2026-08-21 | Action script `cleanup_logs_and_db.ps1` does not exist. Engine self-cleans logs (30 d) + CSVs (7 d). | Engine built-in retention |

## UNTOUCHED

| Task | State | Note |
|---|---|---|
| JarvisOS_15Min_LeadsSkiptrace | Disabled (pre-existing) | Left as-is |
| OpenClaw Gateway | Ready (logon) | Personal gateway infra, out of MBM scope, healthy |

## Collision protection (scheduler-level)

All kept tasks have `MultipleInstancesPolicy=IgnoreNew` and execution caps < trigger interval:
PacedPublisher 15 min/45-min cap → cap > interval is intentional (pace gate decides); LeadEngine 4 h/2 h; Revenue 6 h/2 h. Cross-task collisions eliminated by disabling the duplicate cycles and the watchdog force-starter.
