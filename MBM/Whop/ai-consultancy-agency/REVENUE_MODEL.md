# REVENUE MODEL — AI Consultancy Sprint

> All figures use the offer prices: Audit $297, Build & Deploy $1,497, Managed $497/mo.

## ASSUMPTIONS
- Outbound pool: 200 verified, callable real businesses.
- Audit → Build upsell rate: 25% (every 4 audits converts 1 to $1,497).
- Build → Managed rate: 50% (every 2 builds converts 1 to $497/mo).
- Cold outbound reply rate: ~8%; close rate Audit: ~3% of touched.
- Delivery capacity (manual, first 10): 1 audit/2 days → ~10 audits in 20 days.
- Margin ~95% (cost = our time + already-built assets).

## FIRST $100
- 1 Audit sale @ $297 = $297 → exceeds $100.
- Customers needed: 1. Conversion assumption: 3% of ~35 touched.
- DELIVERY: 72h manual audit. Upsell: Build & Deploy.

## FIRST $1,000
- 4 Audits @ $297 = $1,188. (Or 1 Build @ $1,497.)
- Customers needed: 4 (or 1 Build).
- DELIVERY CAPACITY: 4 audits in ~8 days, manual. Upsell path: 1 of 4 → Build.

## FIRST $5,000
- Mix: 10 Audits ($2,970) + 2 Builds ($2,994) = $5,964.
- Customers needed: 10 audits + 2 builds = 12 total.
- Upsell path: 2 builds → 1 Managed ($497/mo recurring begins).
- DELIVERY: ~3 weeks manual; start delegating audit template.

## FIRST $10,000
- Mix: 15 Audits ($4,455) + 4 Builds ($5,988) + 1 Managed mo ($497) = $10,940.
- Customers needed: 15 + 4 + 1 = 20.
- Upsell path: 4 builds → 2 Managed ($994/mo recurring).
- DELIVERY: ~4–5 weeks; systematize audit delivery with template + scripts.

---

## ESTIMATED vs VERIFIED

### ESTIMATED (modeled from assumptions above)
- First $100: 1 customer, ~35 prospects touched.
- First $1,000: 4 customers.
- First $5,000: 12 customers + 1 recurring.
- First $10,000: 20 customers + 2 recurring.

### VERIFIED (must be updated after live sales — pull from Whop)
- Whop memberships + revenue: run `python MBM/Whop/whop_monetize.py report`.
- Real audits delivered: count in hub Files / chat.
- Real Managed MRR: count active $497 memberships.
- Until first live sale, ALL revenue numbers are ESTIMATED. Mark VERIFIED only after
  Whop `report` shows a paid membership.

> Stop condition: do NOT launch a second offer until FIRST PAYING CUSTOMER = YES
> (Whop membership status = active, payment received).
