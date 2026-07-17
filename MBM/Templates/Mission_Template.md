# Mission: [Insert Mission Name]

- **Objective:** [Clear revenue-driven goal (e.g., "Scrape 100 tax-delinquent property owners")]
- **Customer/Target:** [e.g., BAGA, MBM Internal]
- **Deadline:** [Date/Time]

## Execution Checklist
- [ ] **Action 1: Target Ingestion**
  - Receive specific parameters from human operator.
- [ ] **Action 2: Evidence Collection**
  - Execute `Lead_Research_Workflow.md`.
  - Deliverable: `MBM/Artifacts/raw_leads_[Name].csv`
- [ ] **Action 3: Revenue Qualification**
  - Execute `Qualification_Process.md` on the raw artifact.
  - Deliverable: `MBM/Artifacts/qualified_leads_[Name].csv`
- [ ] **Action 4: Final QA Audit**
  - Execute `QA_Checklist.md`.
  - Deliverable: Approved lead pack moved to `MBM/Clients/[Client]/`.
- [ ] **Action 5: Retrospective & KPI Logging**
  - Calculate execution metrics (Speed, Yield, Defect Rate).
  - Append a new row to `MBM/Logs/KPI_Tracker.csv` for each skill.
  - Document workflow friction and success patterns into `MBM/LessonsLearned/[Mission_Name]_Retro.md`.

## Success KPI
[Specific measurable outcome, e.g., BAGA explicitly states: "Send me another batch."]
