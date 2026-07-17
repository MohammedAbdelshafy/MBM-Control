# Lead Research Workflow

## Objective
To extract raw, high-potential property records from public or subscription data sources (e.g., PropStream) ensuring speed, volume, and adherence to targeting criteria.

## Process

**1. Receive Target Parameters**
- Obtain specific zip codes, property filters (e.g., Tax Default, Vacant, Pre-Foreclosure), and minimum equity thresholds from the Mission Document.

**2. Data Extraction**
- **Manual/UI Action:** Use `browser_subagent` to navigate the data provider, apply the exact filters, and export the list.
- **API/Script Action:** Execute local Python scripts to query public APIs or internal databases using the provided parameters.
- **Constraints:** Never guess or expand parameters outside the mission scope without human authorization.

**3. Artifact Generation**
- Save the raw extracted dataset as a CSV file to `MBM/Artifacts/`.
- Naming convention: `raw_leads_[YYYY-MM-DD]_[CampaignName].csv`.

**4. Evidence Logging**
- Log the data source URL, filter settings applied, and the total count of records retrieved into the `Decision_Log.md` for verifiable proof.
