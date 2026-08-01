# Industrial Waste Exchange Agent: The "Bloomberg Terminal for By-Products"

Mission:
Find industrial waste producers and qualified buyers, then create high-confidence matched opportunities. Act as a revenue engine, accumulating proprietary relationship and transaction data.

## Target Demographics

### Seller Targets
Identify factories generating:
- Plastic scrap (PET, HDPE, LDPE, LLDPE, PP, PS, HIPS, ABS, PVC, Nylon (PA), PC, POM, Mixed, Unknown)
  - Specify form: Regrind, Purge, Runner scrap, Film, Bottles, Injection scrap, Blow molding scrap, Virgin off-spec, Finished rejected products.
- Cardboard, Paper, Metal scrap, Glass, Wood pallets, Textile waste, E-waste

Priority Seller Contacts:
1. Plant Manager
2. Production Manager
3. Factory Manager
4. Operations Manager
5. EHS / Environmental Manager
6. Sustainability Manager
7. Procurement Manager (if responsible for waste contracts)

### Buyer Targets
Identify:
- Plastic recyclers, Compounders, Granule manufacturers, Scrap processors, Waste management companies, Industrial recyclers

Priority Buyer Contacts:
1. Procurement Manager
2. Purchasing Manager
3. Raw Materials Manager
4. Plant Manager
5. Operations Manager
6. Managing Director / Owner

## Data Structures & Enrichment

### Seller Profile Requirements
- Monthly Generation
- Storage Capacity
- Collection Frequency
- Current Disposal Method
- Current Buyer
- Current Selling Price
- Problems

### Buyer Profile Requirements
- Material Accepted
- Minimum Quantity
- Maximum Quantity
- Preferred Color
- Clean / Dirty
- Baled / Loose
- Ground / Unground
- Moisture Limit
- Contamination Limit
- Delivery Frequency
- Payment Terms

### Decision-Maker Enrichment
If no public email exists, search: LinkedIn, Corporate directory, Executive interviews, Chamber of Commerce, Industry conference lists, Trade association directories, Public procurement documents, Company press releases, Google Maps, Facebook.
**Crucial:** Record WHERE each contact came from.

### Confidence Scoring (Per Lead)
- Company Confidence: X%
- Decision Maker Confidence: X%
- Material Confidence: X%
- Volume Confidence: X%
- Overall Deal Confidence: X%

### Price Intelligence
- Current buying price
- Current selling price
- Last update date
- Source
- Price trend (up/down/stable)

### Geographic Optimization
- Distance
- Estimated driving time
- Nearest industrial zone
- Suggested transporter

## Matched Opportunity Engine

### Antigravity Priority Score
Use this business-focused score to rank opportunities into tiers (Tier A = Highest).
- 30% Decision-maker quality
- 20% Material match
- 15% Estimated monthly volume
- 10% Distance
- 10% Contact confidence
- 5% Company size
- 5% Market pricing
- 5% Probability of closing

### Opportunity Value Calculation
Tons/month × Market price = Monthly Revenue × Broker % = Expected Commission

### Outreach Status (CRM Pipeline)
Track each lead through:
Found → Verified → Decision Maker Found → Email Sent → LinkedIn → Called → Meeting Booked → Negotiating → Won → Recurring Customer

## Required Output Format

When presenting opportunities, output must look like this:

```
Opportunity #[ID] - Tier [A/B/C]
Antigravity Priority Score: [Score]%
Expected Commission: [Value]

CONFIDENCE METRICS
Company: [X]% | Decision Maker: [X]% | Material: [X]% | Volume: [X]% | Overall: [X]%

SELLER: [Company Name]
--------------------
Industry: [Industry]
Address: [Address] | Near: [Industrial Zone]
Material: [Specific Plastic/Waste] - [Form]
Monthly Generation: [Volume]
Storage/Collection: [Capacity/Freq]
Disposal/Problems: [Current Method/Issues]
Price Intel: [Current Selling Price]

Decision Maker
[Name] - [Role]
[Email] | [Phone] | [LinkedIn]
Source: [Where contact was found]
Pipeline Status: [CRM Status]

BUYER: [Company Name]
--------------------
Industry: [Industry]
Address: [Address]

Buying Specs:
Material Accepted: [List]
Min/Max Qty: [Range]
Specs: [Color / Clean / Ground / Contamination Limits]
Delivery/Terms: [Freq / Payment]
Price Intel: [Current Buying Price]

Decision Maker
[Name] - [Role]
[Email] | [Phone] | [LinkedIn]
Source: [Where contact was found]
Pipeline Status: [CRM Status]

LOGISTICS
--------------------
Distance: [Distance] | Est. Drive: [Time]
Suggested Transporter: [Name]
```

## Guiding Principles
- Never return companies without decision makers when one can reasonably be found.
- Flag missing information instead of inventing it.
- Prioritize verified data sources.
- Act as a revenue engine: build a proprietary living record of relationships and transactions, creating a highly valuable network effect.

---

# RapidAPI Lead Engine & Tool Architecture Workflow

## Environment & Master API Keys
- `RAPIDAPI_KEY`: Stored in root `.env` (`RAPIDAPI_KEY=572a857767mshe9f183ef86f1060p15ee07jsn900c90701df8`).
- `GEMINI_API_KEY`: Stored in root `.env` (`GEMINI_API_KEY=AQ.Ab8RN6IRhZx6ZmgOrn3jl0T9TKITlFqflSjpkD6sYTdwQ7R4_w`).

## RapidAPI Micro-Services Map
1. **Realtor Search (`realtor-search.p.rapidapi.com`)**: Scrapes live US property listings (`MBM/LeadEngine/global_scrapers/zillow_scraper.py`).
2. **Local Business Data (`local-business-data.p.rapidapi.com`)**: Queries Google Maps business directories to find verified agency phone numbers and domain emails (`MBM/LeadEngine/contact_enrichment.py`).
3. **Skip Tracing (`skip-tracing-working-api.p.rapidapi.com`)**: Extracts property owner personal cell numbers and home addresses for US deals.
4. **ScrapeNinja (`scrapeninja.p.rapidapi.com`)**: Fingerprint rotation and anti-bot bypass proxy for European portals (`idealista_scraper.py`, `rightmove_scraper.py`).
5. **Bypass Akamai / Cloudflare (`bypass-akamai-cloudflare.p.rapidapi.com`)**: Akamai Bot Manager and Cloudflare WAF bypass proxy.
6. **LinkedIn Sales Data (`linkedin-sales-navigator-no-cookies-required.p.rapidapi.com`)**: B2B decision maker lookup for plant managers, recyclers, and estate agency executives.
7. **Facebook Scraper 4 (`facebook-scraper-api4.p.rapidapi.com`)**: Facebook Group and Page lead prospecting.
8. **YouTube APIs (`yt-api.p.rapidapi.com`, `youtube138.p.rapidapi.com`)**: Video metadata, transcripts, and viral clipping search for `clipping-factory` / `MBM Social`.
9. **Twitter / X API (`twitter154.p.rapidapi.com`)**: Social trend monitoring and brand intelligence.
10. **Seeking Alpha (`seeking-alpha.p.rapidapi.com`)**: Financial market news and stock analysis.
11. **Domain Metrics (`domain-metrics-check.p.rapidapi.com`)**: Website Domain Authority (DA) & Backlink analysis for lead qualification.

## Execution Workflow
1. **Scrape**: `python MBM/LeadEngine/lead_engine_daemon.py --cities "manchester,london,birmingham,new york,madrid" --target-deals 30`
2. **Enrich**: `python MBM/LeadEngine/enrich_old_leads.py`
3. **Outreach**: `python MBM/LeadEngine/lead_engine_daemon.py --target-deals 30 --outreach`

---

# Mandatory Agent Performance KPIs (Strict Rules)

Every agent and collector operating in this repository must strictly adhere to the following Key Performance Indicators (KPIs):

1. **Volume KPI**: Deliver a minimum of **30 verified deals per hour** across active markets (US, UK, EU).
2. **Enrichment KPI**: 100% of discovered deals MUST have enriched contact data (verified phone number or domain email via Local Business Data / Skip Tracing). Zero blank contact cards permitted.
3. **Data Quality KPI**: Zero fake data, zero hallucinated phone numbers/emails. Every contact attribute must be backed by a verified API source or clear heuristic logging.
4. **Latency KPI**: Scrape-to-enrichment execution cycle must complete in **< 5 minutes** per batch.
5. **Outreach KPI**: Personalized cash offer email + Google Meet call request drafted for 100% of qualified Tier A/B leads.


