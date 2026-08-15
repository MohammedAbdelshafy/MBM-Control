/**
 * MONEY MODE — SALES ENGINE ACTIVATION (Batch 1)
 *
 * Generates the controlled dialer batches from the ACTIVE dialer dataset
 * (`mbm-dialer/app/public/leads_database.json`) — frozen to a deterministic
 * snapshot first — applying the committed evidence gate + owner routing and
 * assembling HONEST cards:
 *
 *   - No stored `Call_Script`/`Pain_Frame`/`Value_Frame` claims are copied —
 *     stored scripts assert facts (property interest, lost-appointment
 *     counts, "zero dropped calls") that the NPI evidence source does NOT
 *     contain.
 *   - Objection/closing lines are discovery-first; no ROI/pain assertions.
 *   - A record whose stored `sales_lane` (PROPERTY_OWNER / SERVICE_BUSINESS)
 *     asserts facts absent from the NPI source is routed to
 *     VERIFICATION_REQUIRED — never dialed under a fabricated motion.
 *
 * Outputs:
 *   logs/money-mode-2026-08-15.json  — full batch + cards + gate + metrics
 *   logs/money-mode-2026-08-15.txt   — human-readable one-screen cards
 *   logs/money-mode-outcomes-2026-08-15.json — outcome capture scaffold
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import {
  AiVibeDedupeGate,
  classifyOwnerTitle,
  normalizePhone,
  routeDecisionMaker,
  tierRank,
} from '../src/verticals';
import type { AiVibePayload, OwnerRoutingResult } from '../src/verticals';

// ── Constants ────────────────────────────────────────────────────────

const SNAPSHOT_PATH =
  process.env.MONEY_MODE_SNAPSHOT ||
  path.resolve(__dirname, '..', 'logs', 'money-mode-snapshot-2026-08-15.json');
const OUT_DIR = path.resolve(__dirname, '..', 'logs');
const DATE = new Date().toISOString().slice(0, 10);

const OUTCOME_CODES = [
  'CONNECTED',
  'RIGHT_PERSON',
  'WRONG_PERSON',
  'BAD_NUMBER',
  'DNC',
  'NOT_INTERESTED',
  'CALLBACK',
  'INTERESTED',
  'DISCOVERY',
  'DEMO_BOOKED',
  'PROPOSAL',
  'CLOSED_WON',
  'CLOSED_LOST',
] as const;

interface DialerRecord {
  id: string;
  company: string;
  contact: string;
  title: string;
  sales_lane: string;
  owner_status: string;
  source_class: string;
  decision_maker_confidence: string;
  contact_confidence: string;
  phone: string;
  vertical: string;
  stage: string;
  deal_score: number;
  callability_score: number;
  pitch_angle: string;
  details: Record<string, unknown> & {
    priority?: string;
    verified_phone?: string;
    Owner_Name?: string;
    Title?: string;
    Why_This_Deal?: string;
    Known_Signal?: string;
    Discovery_Questions?: string[];
    Next_Action?: string;
    source?: string;
  };
  skip_trace_status: string;
  skip_trace_source: string;
  skip_trace_confidence: string;
}

interface MoneyModeCard {
  id: string;
  owner: string;
  company: string;
  vertical: string;
  salesLane: string;
  storedLane: string;
  phone: string;
  dealScore: number;
  callabilityScore: number;
  ownerRouting: OwnerRoutingResult;
  ownerTier: string;
  whyThisLead: string;
  evidenceSignal: string;
  recommendedOffer: string;
  opening: string;
  discoveryQuestions: string[];
  objectionPaths: Array<{ trigger: string; response: string }>;
  trialClose: string;
  finalClose: string;
  nextAction: string;
  evidenceGate: { pass: boolean; reason: string | null };
  source: string;
}

const LANE_NOT_SUPPORTED = new Set(['PROPERTY_OWNER', 'SERVICE_BUSINESS']);

// ── Helpers ──────────────────────────────────────────────────────────

function h(first: string): string {
  return first.charAt(0).toUpperCase() + first.slice(1).toLowerCase();
}

function ownerDisplayName(record: DialerRecord): string {
  const n = record.details.Owner_Name?.trim();
  if (n && n !== record.company.toUpperCase()) return n;
  if (record.contact && record.contact !== record.company.toUpperCase()) return record.contact;
  return record.company;
}

function evidenceSignal(record: DialerRecord): string {
  return (
    `Verified ${record.source_class} healthcare business (${record.details.source || 'US CMS NPI registry'})` +
    `; skip-trace ${record.skip_trace_status}; decision-maker confidence ${record.decision_maker_confidence};` +
    ` contact confidence ${record.contact_confidence}.`
  );
}

function whyThisLead(record: DialerRecord): string {
  const stored = record.details.Why_This_Deal?.trim();
  if (stored && !/property|interest|recorded/i.test(stored)) return stored;
  return `Verified ${record.source_class} business (${record.details.source || 'NPI'}) with a verified phone and recorded owner contact.`;
}

function recommendedOffer(record: DialerRecord): string {
  return record.pitch_angle || 'AI front-desk automation';
}

function opening(record: DialerRecord): string {
  const owner = ownerDisplayName(record);
  const q = (record.details.Discovery_Questions ?? [])[0] ?? 'How are you currently handling your front-desk calls and patient follow-ups?';
  return (
    `Hi ${owner}, this is Omar with MBM Systems. I help healthcare practices in Texas automate their ` +
    `front desk and patient recall. Before I explain anything — quick question: ${q.replace(/^\d+\.\s*/, '')}`
  );
}

function discoveryQuestions(record: DialerRecord): string[] {
  const stored = record.details.Discovery_Questions ?? [];
  if (stored.length >= 3) return stored.slice(0, 3);
  return [
    'How are after-hours and missed calls currently handled?',
    'How do you follow up with patients who are overdue for visits?',
    'If front-desk automation made sense, would you be open to a 15-minute walkthrough this week?',
  ];
}

const HONEST_OBJECTIONS: Array<{ trigger: string; response: string }> = [
  {
    trigger: 'We already have someone / use AI.',
    response:
      'Totally fair — then the question is just whether what you have covers the after-hours calls and patient follow-ups that slip through. If it does, tell me straight and I will not waste your time.',
  },
  {
    trigger: 'Not interested.',
    response:
      'Understood, and I respect a straight answer. Is it “not this”, or “not right now”? If it is timing, I will follow up once and leave it there.',
  },
  {
    trigger: 'Too busy / call later.',
    response:
      'That is exactly why this call is short. When is a better time — today after 3, or tomorrow morning? I will keep it to two minutes and reschedule if you are mid-fire.',
  },
];

function trialClose(record: DialerRecord): string {
  const owner = ownerDisplayName(record);
  return `If this made sense for ${record.company}'s front desk, would you be open to a 15-minute walkthrough this week — no obligation either way?`;
}

function finalClose(record: DialerRecord): string {
  const owner = ownerDisplayName(record);
  return `I am not asking for a decision today, ${owner}. I am asking for a calendar slot — Tuesday afternoon or Thursday morning, whichever works. Which is better?`;
}

// ── Main ─────────────────────────────────────────────────────────────

function main(): void {
  if (!fs.existsSync(SNAPSHOT_PATH)) {
    console.error(`status: failure — snapshot not found at ${SNAPSHOT_PATH}`);
    process.exit(1);
  }

  const records = JSON.parse(fs.readFileSync(SNAPSHOT_PATH, 'utf8')) as DialerRecord[];
  const gate = new AiVibeDedupeGate();
  const suppressed: Array<{ id: string; company: string; reason: string | null }> = [];
  const verificationRequired: Array<{ id: string; company: string; storedLane: string; reason: string }> = [];
  const dialable: Array<{ record: DialerRecord; routing: OwnerRoutingResult; gateReason: string | null }> = [];

  for (const record of records) {
    const payload: AiVibePayload = {
      company: record.company,
      phone: record.details.verified_phone ?? record.phone,
      owner_name: record.details.Owner_Name ?? record.contact,
      title: record.details.Title ?? record.title,
      vertical: record.vertical,
      source: record.details.source ?? 'US_CMS_NPI',
    };
    const check = gate.admit(payload);

    if (!check.pass) {
      suppressed.push({ id: record.id, company: record.company, reason: check.reason });
      continue;
    }

    // A stored lane whose motion asserts facts the NPI source cannot back
    // (property ownership, property management) can never be dialed under
    // that motion. Route to verification until real ownership evidence exists.
    if (LANE_NOT_SUPPORTED.has(record.sales_lane)) {
      verificationRequired.push({
        id: record.id,
        company: record.company,
        storedLane: record.sales_lane,
        reason:
          `Stored lane "${record.sales_lane}" asserts ${record.sales_lane === 'PROPERTY_OWNER' ? 'property ownership' : 'property-management operations'} ` +
          `not present in the NPI evidence source; requires county/ownership verification before any property motion is dialed.`,
      });
      continue;
    }

    const routing = routeDecisionMaker({
      name: record.details.Owner_Name ?? record.contact,
      title: record.details.Title ?? record.title,
      source: record.details.source ?? 'US_CMS_NPI',
    });
    dialable.push({ record, routing, gateReason: check.reason });
  }

  // Rank: owner tier desc, then priority, deal score, callability, then a
  // deterministic tiebreak (company name).
  const ranked = dialable
    .sort((a, b) => {
      const pa = a.record.details.priority ?? '2';
      const pb = b.record.details.priority ?? '2';
      return (
        tierRank(b.routing.tier) - tierRank(a.routing.tier) ||
        pa.localeCompare(pb) ||
        b.record.deal_score - a.record.deal_score ||
        b.record.callability_score - a.record.callability_score ||
        a.record.company.localeCompare(b.record.company)
      );
    })
    .map(({ record, routing }) => ({ record, routing }));

  const callNow = ranked.slice(0, 25);
  const next75 = ranked.slice(25, 100);
  const remaining = ranked.slice(100);

  function buildCard(entry: { record: DialerRecord; routing: OwnerRoutingResult }): MoneyModeCard {
    const { record, routing } = entry;
    const phone = record.details.verified_phone ?? record.phone;
    return {
      id: record.id,
      owner: ownerDisplayName(record),
      company: record.company,
      vertical: record.vertical,
      salesLane: 'AI_BUSINESS_OWNER',
      storedLane: record.sales_lane,
      phone,
      dealScore: record.deal_score,
      callabilityScore: record.callability_score,
      ownerRouting: routing,
      ownerTier: routing.tier,
      whyThisLead: whyThisLead(record),
      evidenceSignal: evidenceSignal(record),
      recommendedOffer: recommendedOffer(record),
      opening: opening(record),
      discoveryQuestions: discoveryQuestions(record),
      objectionPaths: HONEST_OBJECTIONS,
      trialClose: trialClose(record),
      finalClose: finalClose(record),
      nextAction: record.details.Next_Action ?? 'CALL_AI_BUSINESS_OWNER_DECISION_MAKER',
      evidenceGate: { pass: true, reason: null },
      source: record.details.source ?? 'US_CMS_NPI',
    };
  }

  const cards = [...callNow, ...next75].map(buildCard);

  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  const jsonPath = path.join(OUT_DIR, `money-mode-${DATE}.json`);
  const txtPath = path.join(OUT_DIR, `money-mode-${DATE}.txt`);

  const report = {
    status: 'success',
    timestamp: new Date().toISOString(),
    inputs: {
      snapshotPath: SNAPSHOT_PATH,
      snapshotRecords: records.length,
      controlledBatchSize: 25,
    },
    partition: {
      callNow: callNow.length,
      next75: next75.length,
      verificationRequired: verificationRequired.length,
      suppressed: suppressed.length,
      remainingDialableNotScheduled: remaining.length,
    },
    lanes: {
      honestLaneDialed: 'AI_BUSINESS_OWNER',
      storedLanesInDataset: Object.entries(
        records.reduce<Record<string, number>>((m, r) => {
          m[r.sales_lane] = (m[r.sales_lane] ?? 0) + 1;
          return m;
        }, {}),
      ).map(([lane, count]) => ({ lane, count })),
      storedLanesNotSupportedByEvidence: Array.from(LANE_NOT_SUPPORTED),
    },
    cards,
    verificationRequired,
    suppressed,
    metrics: {
      outcomesRecorded: 0,
      conversionRate: 'INSUFFICIENT_DATA',
      revenue: 'INSUFFICIENT_DATA',
      bestVertical: 'INSUFFICIENT_DATA',
      bestOffer: 'INSUFFICIENT_DATA',
      bestScript: 'INSUFFICIENT_DATA',
      note: 'No real dialing has occurred yet (only dry-run/simulated dispositions). Metrics are reported only from real outcomes.',
    },
    outcomeCodes: OUTCOME_CODES,
    next_action: 'Dial CALL NOW 25 via close_queue_dialer.py; log outcomes with the 13 outcome codes; feed results back into callability.',
    owner: 'system',
  };

  fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2));

  const blocks = cards.map((card, i) =>
    [
      `═══════════════════════════════════════════`,
      `#${i + 1} · ${card.ownerRouting.routeLabel} · ${card.company}`,
      `Vertical: ${card.vertical} · Lane: ${card.salesLane} · ${card.ownerTier}`,
      `Callability: ${card.callabilityScore}/100 · Deal Score: ${card.dealScore}/100`,
      `Phone: ${card.phone}`,
      ``,
      `WHY THIS LEAD: ${card.whyThisLead}`,
      `EVIDENCE: ${card.evidenceSignal}`,
      `RECOMMENDED OFFER: ${card.recommendedOffer}`,
      ``,
      `OPENER: ${card.opening}`,
      `DISCOVERY: ${card.discoveryQuestions.join('  ')}`,
      `OBJECTIONS:`,
      ...card.objectionPaths.map((o) => `  • ${o.trigger} → ${o.response}`),
      `TRIAL CLOSE: ${card.trialClose}`,
      `FINAL CLOSE: ${card.finalClose}`,
      `NEXT ACTION: ${card.nextAction}`,
      ``,
    ].join('\n'),
  );
  fs.writeFileSync(txtPath, blocks.join('\n'));

  const outcomesPath = path.join(OUT_DIR, `money-mode-outcomes-${DATE}.json`);
  const outcomes = {
    status: 'success',
    timestamp: new Date().toISOString(),
    codes: OUTCOME_CODES,
    records: [],
    metrics: {
      outcomesRecorded: 0,
      conversionRate: 'INSUFFICIENT_DATA',
      revenue: 'INSUFFICIENT_DATA',
    },
    note: 'Outcome capture scaffold. Populate `records` with { id, phone, code, notes, ts } for each real dial.',
  };
  fs.writeFileSync(outcomesPath, JSON.stringify(outcomes, null, 2));

  console.log(
    JSON.stringify(
      {
        status: 'success',
        timestamp: new Date().toISOString(),
        inputs: { snapshotRecords: records.length, controlledBatchSize: 25 },
        outputs: {
          callNow: callNow.length,
          next75: next75.length,
          verificationRequired: verificationRequired.length,
          suppressed: suppressed.length,
          remainingDialableNotScheduled: remaining.length,
          cardsBuilt: cards.length,
          jsonPath,
          txtPath,
          outcomesPath,
        },
        metrics: { outcomesRecorded: 0, conversionRate: 'INSUFFICIENT_DATA' },
        next_action: 'Dial CALL NOW 25; log outcomes; feed back into callability.',
        owner: 'system',
      },
      null,
      2,
    ),
  );
}

main();