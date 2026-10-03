# MBM-Control: Sales-Ready Evidence Pack
**Truthful Capabilities, Architecture, Provenance & Delivery Specifications**  
**Operating Standard:** Zero Fabrication / Verified Evidence Only  
**Last Verified:** September 3, 2026  

---

## 1. Subsystem Architecture Overview

MBM-Control operates three primary productized technical pipelines designed for enterprise and agency buyers:

```
[ CMS NPPES Registry API v2.1 ] ──> [ NPPESSourceAdapter ] ──> [ LeadProvenanceGate ] ──> [ lead_pack_builder.py ] ──> CSV + Brief
[ Raw Video Media (.mp4 / YT) ]  ──> [ Candidate Scoring ] ──> [ ffmpeg 9:16 Reframe ]  ──> [ Subtitle Burn-in ]   ──> YouTube Studio
[ County ArcGIS Assessor API ]  ──> [ ownership_verifier ] ──> [ APN / Tax Match ]      ──> [ Deal Dossier ]        ──> Investor Report
```

All data processing is governed by strict deterministic gates (`LeadProvenanceGate`) that reject synthetic numbers, sequential fixture names, and placeholder emails.

---

## 2. Product 1: Healthcare B2B Practice Call Sheets

### What It Solves
B2B medical software sales teams, healthcare marketing agencies, and clinical recruiters waste hours filtering through scraped directories containing 555-exchanges, disconnected switchboards, and outdated provider listings.

### Source & Provenance Chain
- **Primary Source:** Centers for Medicare & Medicaid Services (CMS) National Plan & Provider Enumeration System (NPPES) Registry API v2.1 (`https://npiregistry.cms.hhs.gov/api/`).
- **Identifier Verification:** Every 10-digit National Provider Identifier (NPI) is mathematically validated using the ISO/IEC 7812 Luhn check-digit algorithm with health industry prefix `80840`.
- **Phone Validation:** Every telephone number is standardized to E.164 (`+1XXXXXXXXXX`) and verified against North American Numbering Plan (NANP) specifications ($NXX-NXX-XXXX$, $N \in [2-9]$, excluding reserved 555 and 000 exchanges). Low-entropy sequences ($\le 4$ unique digits) are purged.
- **Provenance Stamp:** Every record carries an explicit provenance block (`source="CMS NPI Registry API v2.1"`, `verification_method="npi_registry_api"`, `retrieved_at=ISO8601`).

### Sanitized Sample Output
View full sample: [`docs/samples/sample_healthcare_callsheet.csv`](file:///c:/Users/omare/OneDrive/Desktop/AI/docs/samples/sample_healthcare_callsheet.csv)

| Field | Example Record |
|---|---|
| **NPI** | `1568833093` (Valid CMS Luhn check digit) |
| **Organization Name** | Advantage Medical Group LLC |
| **Specialty (Taxonomy)** | Internal Medicine |
| **Authorized Official** | Torres Carlos (Managing Partner) |
| **Practice Address** | 1200 Medical Parkway, Ste 300, Dallas, TX 75235 |
| **Practice Telephone** | `+17873068356` (NANP-compliant E.164) |
| **Provenance Source** | CMS NPI Registry API v2.1 |

### Real Technical Limitations (What We Do NOT Claim)
1. **Not Live-Dialed:** Telephone numbers are self-reported by the provider on federal filings. We do not place live robocalls or ping carrier switches to verify instantaneous ring status.
2. **Practice Switchboard vs Direct Mobile:** The reported number is the primary practice location telephone; it may connect to clinic reception rather than the physician's personal mobile line.
3. **Buyer Compliance Responsibility:** Buyers must use the data in accordance with applicable B2B marketing, TCPA, and CAN-SPAM regulations.

---

## 3. Product 2: Crayo-Class Autonomous Video Content Engine

### What It Solves
Content creators, agency owners, and podcasters spend 15–20 hours each week manually scrubbing audio waveforms, finding hooks, formatting 9:16 vertical crops, and creating animated captions.

### Pipeline & Capabilities
- **Candidate Pool Scoring:** Analyzes long-form transcripts across 8 axes (hook strength, emotional valence, speech tempo, viral pattern match, audio clarity, drop-off risk inverse) to extract optimal 30–60 second segments.
- **Dynamic 9:16 Reframing:** Automatically centers 16:9 landscape frames into 1080x1920 vertical canvas via ffmpeg filter chains (`crop=in_h*(9/16):in_h:...`).
- **Word-Level Subtitle Burn-in:** Generates animated `.ass` subtitle layers featuring custom typography (`Outfit-Bold`), primary color styling, and word-pop scale animations.
- **Content Intelligence:** Uses local/hosted LLMs to craft viral hook headlines, YouTube Shorts titles, and hashtag clusters.
- **Publishing Boundary:** Automated scheduled upload is currently implemented and tested for **YouTube Studio**. TikTok and Instagram packages are rendered and exported for manual creator publishing.

### Sanitized Execution Spec
View full sample: [`docs/samples/crayo_clip_production_spec.json`](file:///c:/Users/omare/OneDrive/Desktop/AI/docs/samples/crayo_clip_production_spec.json)

---

## 4. Product 3: Dallas County Property Ownership Intelligence

### What It Solves
Real estate wholesalers and land acquisition teams waste marketing capital sending direct mail to incorrect owners, deceased individuals, or multi-owner parcels with conflicting deed records.

### Authority & Evidence Chain
- **Authoritative Gateway:** Dallas Central Appraisal District (DCAD) ArcGIS REST endpoint (`https://gis.dallascad.org/arcgis/rest/services/...`).
- **Parcel Resolution:** Matches site address to certified county tax appraisal rolls, extracting exact parcel APN, deeded owner-of-record, land assessed valuation, improvement valuation, and owner mailing address.
- **Conflict Handling:** If multiple conflicting owners or split parcels are returned for a single address, the pipeline automatically flags the record as `CONFLICT` and quarantines it from auto-dialing.

### Sanitized Sample Output
View full sample: [`docs/samples/sample_dcad_deed_audit.md`](file:///c:/Users/omare/OneDrive/Desktop/AI/docs/samples/sample_dcad_deed_audit.md)

---

## 5. Security, Secret Hygiene & Privacy Controls

1. **Zero Secret Leakage:**
   - All external provider API keys (`NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `BYTEZ_API_KEY`, `GROQ_API_KEY`, `WHOP_API_KEY`) are loaded via local `.env` which is covered by `.gitignore`.
   - Comprehensive regex scanning verifies zero tokens present in source code, committed files, or logs.
2. **Local Sovereignty / Zero-Outbound Mode:**
   - The Unified AI Router supports `PrivacyPolicy.LOCAL_ONLY_NO_OUTBOUND`, completely blocking cloud API transmission and running purely through local Ollama (`http://localhost:11434`).
3. **Deterministic Single-Writer Lock:**
   - Lead database mutations enforce a file-system mutex (`MBM.GLM.single_writer_lock.DialerSingleWriter`) with zero-shrinkage verification to ensure dataset integrity.

---

## 6. Commercial Terms & Engagement Process

1. **Demonstration Phase (No Cost):**
   - Prospective clients receive a 5-record sanitized sample or 1 sample video clip demonstration matching their exact parameters.
2. **Order Placement:**
   - B2B digital packages and monthly retainers are billed in USD via the canonical Neteller wallet (`abdelshafyclapps@gmail.com`) or the Whop marketplace.
3. **Delivery Mechanism:**
   - Lead packages: Delivered as secure digital downloads containing CSV file, provenance brief, and SHA-256 data manifest.
   - Video retainers: Delivered via Google Drive shared folder or direct scheduled publishing to client YouTube channels.
