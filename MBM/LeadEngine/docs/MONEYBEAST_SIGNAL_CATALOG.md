# MoneyBeast Signal Catalog

Evidence-backed motivated-seller signals. A signal is only counted when it is
observed in a record (never inferred from aggregates). Missing data stays
missing and is flagged `REQUIRES_VERIFICATION`.

## Distress (Hot100)

| Signal key | Weight | Evidence source |
|---|---|---|
| `auction` | 32 | sheriff/foreclosure sale calendar; auction_date field |
| `foreclosure` | 30 | county recorder / foreclosure filing index |
| `reo` | 28 | bank-owned (REO) record |
| `tax_delinquent` | 25 | county treasurer / tax delinquency portal |
| `bankruptcy` | 22 | public bankruptcy docket (property interest) |
| `probate` | 20 | probate court index |
| `inherited` / `estate` | 15 / 12 | probate/estate record |

## Seller fatigue / pre-distress (Growth200)

| Signal key | Weight | Evidence source |
|---|---|---|
| `relisted` | 14 | MLS listing history |
| `price_cut` | 12 | listing price history |
| `failed_listing` / `failed_flip` | 12 / 10 | delist->relist cycle |
| `landlord_exit` / `aging_landlord` | 12 / 10 | rental/entity patterns |
| `concessions` | 7 | listing concessions |
| `long_dom` | 8 | days-on-market |

## Occupancy / ownership overlays (stack with the above)

| Signal key | Weight | Evidence source |
|---|---|---|
| `vacant` | 15 | occupancy/public utility signal |
| `absentee` | 10 | owner address != property address |
| `out_of_state` | 8 | owner state != property state |
| `entity` | 6 | owner is LLC/trust/etc |
| `rental_registration` | 18 | municipal rental registry |
| `vacation_rental` | 15 | STR registration/listing |
| `code_concern` | 10 | municipal code enforcement / nuisance |

## Honesty rules

1. A signal requires an evidence source; `signal_evidence` carries it.
2. Aggregate market stats never produce an individual lead.
3. Records without a property address/parcel are capped below Growth200 floor
   (composite < 40) and flagged `REQUIRES_VERIFICATION`.
4. Explicit `STALE` / `CONFLICT` statuses are preserved, never guessed away.
