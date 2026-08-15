---
name: salesforce-crm-copilot
description: Automated CRM pipeline management, opportunity stage progression, call transcript extraction, and weighted revenue forecasting.
---
# Salesforce CRM Copilot Skill

**Goal**: Automate 100% of CRM data entry, opportunity stage movement, and revenue reporting.

## Core Automations:
1. **Call-to-Opportunity Extraction**: Convert unstructured call transcripts and notes into structured JSON deals.
2. **Dynamic Stage Progression**: Advance deals from `Prospecting` $\rightarrow$ `Diagnostic Booked` $\rightarrow$ `Audit SOW Sent` $\rightarrow$ `Closed Won`.
3. **Weighted Pipeline Forecasting**: Compute realtime pipeline value and weighted probability forecasts.
4. **Bi-Directional Cloud Sync**: Sync local SQLite/JSON databases with live Salesforce Cloud instances via `simple-salesforce`.
