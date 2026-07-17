# Agent Performance KPIs

In Operations Mode, every agent is measured by their direct contribution to business value. These KPIs define success for the core execution layer.

## 1. Mission Planner (The Orchestrator)
**Goal:** Translate high-level objectives into atomic, deterministic execution steps.
- **Clarity Score:** Target 100%. Measured by the absence of execution errors caused by vague or undefined checklist items.
- **Speed to Plan:** Target < 2 minutes. The time taken to ingest a ChatGPT prompt and output the formal Mission Document.

## 2. Evidence Collector (The Workhorse)
**Goal:** Gather verifiable, revenue-generating data rapidly.
- **Data Volume:** Target varies by mission (e.g., 50+ records per scrape).
- **Extraction Speed:** Time taken from mission assignment to delivering the raw artifact.
- **Data Integrity:** Target 100%. Zero fabricated records. Measured by the QA failure rate downstream.

## 3. Revenue Review (The Gatekeeper / QA)
**Goal:** Ensure the client (e.g., BAGA) explicitly requests another batch.
- **Defect Rate (Accuracy):** Target 0%. Zero duplicates and 100% verified contacts delivered to the client.
- **Yield Rate:** The percentage of raw leads that successfully pass the qualification criteria (measures the quality of the Collector's targeting).
- **Time to QA:** Time taken to audit the raw artifact and produce the final delivery.

## KPI Tracking Protocol
At the conclusion of every mission (Action: Retrospective), the acting agent must calculate these metrics and log a new row in `MBM/Logs/KPI_Tracker.csv`. Continuous failure to meet KPIs requires a review and refactoring of the failing Skill.
