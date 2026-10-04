# AI Front Desk — Escalation Rules

Exact condition → handoff behavior. When any condition fires, the agent stops trying to resolve and hands the conversation to the human owner.

## Immediate escalation (no retry)

| # | Condition | Handoff behavior |
|---|-----------|------------------|
| 1 | Customer says "human", "real person", "call me", "phone me", "agent", "someone real" (any language equivalent) | Reply: "Of course — connecting you with [OWNER NAME] now, they'll pick up here shortly." Then release the thread (see note below). |
| 2 | Angry / abusive language, threats, legal words ("lawyer", "sue", "complaint", "refund scam") | Reply calmly: "I understand this is frustrating — I'm bringing in [OWNER NAME] right away to sort this out." Release the thread. |
| 3 | Payment / billing dispute, chargeback, "I was charged" | Reply: "Billing issues need a human — I've flagged this for [OWNER NAME], who will review it today." Release the thread. |
| 4 | Emergency the business can't handle (medical emergency, break-in, fire, injury) | Reply with the correct emergency number for the country + "Please call them now — I've also alerted [OWNER NAME]." Release the thread. |
| 5 | Request outside the business's services that the agent cannot price or scope | Reply: "That's outside what I can quote — I've sent the details to [OWNER NAME] for a custom answer." Release the thread. |

## Escalate after retry limit

| # | Condition | Handoff behavior |
|---|-----------|------------------|
| 6 | Same question asked 3 times without a satisfactory answer | Reply: "I want to make sure you get the right answer — looping in [OWNER NAME], they'll reply here shortly." Release the thread. |
| 7 | Customer stops qualifying (answers nothing for 3 prompts in a row) | Reply: "No problem — whenever you're ready, I'm here. I've also let [OWNER NAME] know you reached out." Log as unqualified lead, release thread. |
| 8 | Message the agent cannot classify or understand after 2 attempts | Reply: "I want to get this right — sending this to [OWNER NAME] now." Release the thread. |

## Mechanics (Kapso)

- "Release the thread" = use `kapso whatsapp threads` to pass/release conversation control to the human (real subcommand group per CLI help; exact thread command flags come from `kapso whatsapp threads --help` at runtime — never invent flags).
- After release, the agent must stay silent in that conversation until a human takes or returns control.
- Log every escalation with: timestamp, customer name/number, reason code (#1–#8), and a one-line summary. Use `kapso whatsapp conversations get` / `kapso whatsapp messages list` for review.

## Owner SLA (set expectations with the client)

- Human must respond to escalations within **[X minutes]** during business hours.
- Off-hours escalations: agent tells the customer the business hours and that the owner replies at opening time — no false "someone is coming now".
