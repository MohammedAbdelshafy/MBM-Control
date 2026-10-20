# Cash Offer Letter — Pre-Foreclosure (Oct 2026 Cycle)

**Print instructions:** one page, white/cream paper, hand-written or hand-style
font for the envelope teaser. Merge fields: {OWNER_NAME}, {PROPERTY_ADDRESS},
{CITY}, {AUCTION_DATE}, {OFFER_PRICE}, {SIGNER_NAME}, {SIGNER_PHONE}.

---

**Envelope teaser:** *About your home at {PROPERTY_ADDRESS} — please open*

---

Dear {OWNER_NAME},

My name is {SIGNER_NAME}. I buy houses in the {CITY} area for cash, as-is.

I noticed public records indicate your property at {PROPERTY_ADDRESS} may be
headed for a foreclosure auction on {AUCTION_DATE}. I know this is a difficult
time, and I want you to know you still have options.

**I can offer you ${OFFER_PRICE} in cash for your home — as-is, no repairs, no
realtor fees, no commissions, no waiting on bank approvals.** We can close on
your timeline, even within 7 days if you need. You walk away with cash in your
pocket instead of losing the property at the courthouse steps and getting
nothing.

This is not a listing and there is no obligation — just a real, written cash
offer you can compare against any other option.

If you'd like to talk it through, call or text me directly at {SIGNER_PHONE}.
If I don't hear from you, I won't send another letter.

Wishing you well,

{SIGNER_NAME}
MBM Acquisitions — We buy houses cash, as-is, in Dallas–Fort Worth

---

*Fine print for the back of the letter (small):*
This is a business solicitation from a private buyer. We are not your lender,
not a government agency, and not affiliated with any bank or court. If you do
not wish to receive mail from us, write to the return address above with
"REMOVE" and we will take you off our list permanently.

---

## Merge-file spec

| Column | Source | Example |
|---|---|---|
| owner_name | DCAD/TAD verified owner (never guessed) | Maria Delgado |
| property_address | Auction listing / appraisal district | 123 Main St |
| city | Auction listing | Dallas |
| state | fixed | TX |
| zip | Auction listing | 75216 |
| auction_date | Trustee sale posting (or "the upcoming trustee sale") | November 3, 2026 |
| offer_price | 40% of the list/asking or appraised value, rounded down to nearest $100 | 120000 |
| signer_name | fixed | Mohammed |
| signer_phone | founder's phone (to be filled before printing) | TBD |

If `auction_date` is unverified, use the fallback line: "may be headed for a
foreclosure auction in the near future." If `owner_name` is unverified, use
"Homeowner". Never invent either.
