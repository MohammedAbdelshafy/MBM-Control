# Official County Ownership Sources Registry

Researched 2026-08-15. Each county entry documents the authoritative
assessor / recorder / tax source. `verified: True` endpoints were confirmed
reachable from this environment; `adapter: arcgis` entries are usable by
`property_intel.ownership_verifier.ArcGisAssessorAdapter` with no API key.

## Honesty contract

- A person/entity is only labelled **legal owner** when the official source
  returned it AND the address/APN match is unambiguous.
- When multiple distinct owners match the same address, the verifier returns
  **CONFLICT** (no owner asserted) rather than guessing.
- Counties without a verified adapter return **NOT_FOUND /
  REQUIRES_VERIFICATION** — the pipeline never fabricates an owner.

## Texas (operating market) — verified ArcGIS endpoints

| County | FIPS | Authority | Website | ArcGIS API | Status |
|---|---|---|---|---|---|
| Dallas | 48113 | Dallas Central Appraisal District (DCAD) | dallascad.org | `maps.dcad.org/prdwa/rest/services/Property/ParcelQuery/MapServer/4` | **VERIFIED live** — returns `OWNERNME1/2`, `SITEADDRESS`, `PSTLADDRESS`, `PARCELID` |
| Tarrant | 48439 | TAD / Tarrant County Tax Assessor-Collector | tad.org | `mapit.tarrantcounty.com/arcgis/rest/services/Tax/TCProperty/MapServer/0` | Endpoint reachable; owner LIKE queries confirmed in research |
| Harris | 48201 | Harris Central Appraisal District (HCAD) | hcad.org | `www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer/0` | Endpoint reachable; ambiguous site-address matches → CONFLICT (correct) |
| Collin | 48085 | Collin Central Appraisal District (CCAD) | collincad.org | `gismaps.cityofallen.org/arcgis/rest/services/ReferenceData/Collin_County_Appraisal_District_Parcels/MapServer/1` | Endpoint reachable; slow (~24s) |

Notes:
- **DCAD** is the proven reference implementation. Sample verified 2026-08-15:
  `12124 Schroeder Rd, Dallas` → owner `CHANDLER TAMECA`, parcel `00000719884000000`.
- **Harris** site-address is minimal (`1300 MAIN`) and commonly maps to several
  distinct owners → the adapter returns CONFLICT until an APN/parcel number is
  provided (APN lookup is exact and yields VERIFIED).
- **Collin** owner field requires the joined-table name
  `GIS_DBO_AD_Entity_file_as_name` used verbatim in WHERE clauses.
- Texas Tax Code §25.025 lets protected persons (peace officers, judges,
  domestic-violence victims) suppress owner/address records; such parcels may
  legitimately return NOT_FOUND.

## Texas — official websites only (adapter=none, no confirmed free API)

Ownership for these counties must be verified via the official portal or an
authorized property-data provider; the pipeline reports REQUIRES_VERIFICATION.

| County | FIPS | Authority | Website |
|---|---|---|---|
| Travis | 48453 | Travis Central Appraisal District (TCAD) | travis.parceldata.org |
| Bexar | 48029 | Bexar Appraisal District (BCAD) | bcad.org |
| Williamson | 48491 | Williamson CAD (WCAD) | wcad.org |
| Denton | 48121 | Denton CAD (DCAD-DFW) | dentoncad.com |
| El Paso | 48141 | El Paso CAD (EPCAD) | epcad.org |
| Montgomery | 48339 | Montgomery CAD (MCAD) | mctxcad.org |
| Fort Bend | 48157 | Fort Bend CAD (FBCAD) | fbcad.org |

## Other major US markets — official websites only

| State | County | FIPS | Authority | Website | Notes |
|---|---|---|---|---|---|
| IL | Cook | 17031 | Cook County Recorder of Deeds / Assessor | cookcountyrecorder.com / cookcountypropertyinfo.com | Public ArcGIS layer exposes PIN + street address only (no owner) |
| AZ | Maricopa | 04013 | Maricopa County Assessor | mcassessor.maricopa.gov | |
| CA | Los Angeles | 06037 | LA County Assessor | assessor.lacounty.gov | |
| FL | Miami-Dade | 12086 | Miami-Dade Property Appraiser | miamidade.gov | |
| NV | Clark | 32003 | Clark County Assessor | clarkcountynv.gov | |
| WA | King | 53033 | King County Assessor | info.kingcounty.gov | public data download |
| MI | Wayne | 26163 | Wayne County Assessor | waynecounty.com | |
| OH | Franklin | 39049 | Franklin County Auditor | franklincountyauditor.com | recorder |
| TN | Shelby | 47157 | Shelby County Assessor | assessor.shelby.tn.us | |
| GA | Fulton | 13121 | Fulton County Tax Assessor | fultonassessor.org | |
| NC | Mecklenburg | 37119 | Mecklenburg County Assessor | qpublic.schneidercorp.com | QPublic |
| PA | Philadelphia | 42101 | Philly Office of Property Assessment | property.phila.gov | |

## Adding a county

1. Find the county assessor/recorder website and any public GIS REST service
   (`/arcgis/rest/services/.../MapServer/N` or `/FeatureServer/N`).
2. Append an entry to `county_sources.py` with the layer URL + field map.
3. Set `verified: False` until you have confirmed a live query returns rows.
4. The generic `ArcGisAssessorAdapter` will pick it up automatically once
   `adapter: "arcgis"` and the field map are correct.