# SMS Scripts — Pre-Foreclosure Cash Offer (Oct 2026 Cycle)

**Compliance gate:** SMS sending is BLOCKED until Phound is provisioned (founder
action) and the recipient list is scrubbed against DNC + express-consent rules.
Every message carries an opt-out ("Reply STOP to opt out"). All three variants
are ≤160 characters (single segment) when filled with a typical name/address.
Never text numbers that are skip-trace UNVERIFIED or that bounced.

**Send policy:**
- 1 touch per variant, ≥3 days apart, max 3 touches per number
- Suppress anyone who replied, opted out, or has a negative disposition
  (BAD_NUMBER / WRONG_PERSON / NON_OWNER / DNC) in the call history

---

## Variant 1 — Direct (auction-aware)

> Hi {name}, Mohammed here. Your property at {address} may face auction {date}. I buy homes cash as-is, no fees. Want a free cash offer? Reply STOP to opt out.

Use when: auction date is confirmed for the property. Script variant: OWNER_OCCUPIED.

## Variant 2 — Empathy (situation-aware)

> Hi {name}, Mohammed with MBM here. If foreclosure looms on {address}, I can pay cash as-is and close before the auction. Free offer? Reply STOP to opt out.

Use when: owner shows distress signals (tax delinquent, vacancy, hardship) but no
confirmed auction date yet. Script variant: OWNER_OCCUPIED.

## Variant 3 — Urgent (equity-frame)

> {name} — auction is coming for {address}. I pay cash, close fast, you keep what's left. From Mohammed, MBM. Free offer? Reply STOP to opt out.

Use when: auction date is ≤14 days out. Script variant: OWNER_OCCUPIED.

## Variant 4 — LLC / entity owner

> Hi {name}, Mohammed with MBM. I work with cash buyers acquiring distressed {city} properties as-is before auction. Is {address} something you'd sell? Reply STOP to opt out.

Use when: owner is an LLC or business entity (Harmon-style portfolio owners).
Script variant: LLC_OWNER. (Filled length: ~185 chars with sample data — acceptable
as a 2-segment message only after confirming budget; otherwise shorten manually.)

## Follow-up reply templates

- Interested: "Great — I can put a written cash offer together today. What's the best number and time to talk for 5 minutes?"
- Asks price first: "I make offers based on as-is condition. I can give you a firm number after a quick 5-minute call and a drive-by. When works?"
- Opt-out: "Understood — you won't hear from me again." (log DNC immediately)
- Wrong number: "Sorry about that — I'll remove this number. Thanks." (log WRONG_PERSON)
