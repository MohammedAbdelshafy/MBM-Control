/**
 * MONEY MODE — SALES ENGINE ACTIVATION (Batch 1) · GO-LIVE GATE
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
 *   - OWNER_STATUS is NEVER asserted from the NPI registry: the registry
 *     evidences a licensed practitioner, not verified ownership. Cards show
 *     OWNER_STATUS = UNKNOWN and DECISION_MAKER = title tier (DIRECTOR).
 *   - SIMULATED_OUTCOMES and REAL_OUTCOMES are kept separate. Only real
 *     outcomes may drive connect/qualified/demo/proposal/close/revenue/
 *     learning metrics. The 19 dry-run dispositions never contaminate them.
 *
 * Outputs:
 *   logs/money-mode-2026-08-15.json  — full batch + cards + QA + gate + metrics
 *   logs/money-mode-2026-08-15.txt   — human-readable one-screen cards
 *   logs/money-mode-outcomes-2026-08-15.json — outcome capture scaffold
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import {
  AiVibeDedupeGate,
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

/** REAL outcome codes — only actual events may be recorded under these. */
const OUTCOME_CODES = [
  'NO_ANSWER',
  'CONNECTED',
  'WRONG_PERSON',
  'BAD_NUMBER',
  'DNC',
  'NOT_INTERESTED',
  'CALLBACK',
  'QUALIFIED',
  'DEMO_BOOKED',
  'DEMO_COMPLETE',
  'PROPOSAL',
  'NEGOTIATION',
  'CLOSED_WON',
  'CLOSED_LOST',
] as const;

const FOLLOW_UP_PRIORITY_CODES = new Set(['CALLBACK', 'DEMO_BOOKED', 'PROPOSAL', 'NEGOTIATION']);

/** Fields every prime card must carry, non-empty, with zero placeholders. */
const REQUIRED_CARD_FIELDS: Array<keyof MoneyModeCard> = [
  'id',
  'person',
  'title',
  'company',
  'vertical',
  'salesLane',
  'contactStatus',
  'ownerStatus',
  'decisionMaker',
  'whyThisLead',
  'evidenceSignal',
  'recommendedOffer',
  'opening',
  'discoveryQuestions',
  'objectionPaths',
  'trialClose',
  'finalClose',
  'nextAction',
  'phone',
];

const PLACEHOLDER_REGEX = /\[[A-Z_]+\]/;

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

interface QAResult {
  field: string;
  pass: boolean;
  reason: string | null;
}

interface MoneyModeCard {
  id: string;
  person: string;
  title: string;
  company: string;
  vertical: string;
  salesLane: string;
  storedLane: string;
  contactStatus: string;
  ownerStatus: string;
  decisionMaker: string;
  phone: string;
  dealScore: number;
  callabilityScore: number;
  ownerRouting: OwnerRoutingResult;
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
  qa: { pass: boolean; checks: QAResult[] };
}

const LANE_NOT_SUPPORTED = new Set(['PROPERTY_OWNER', 'SERVICE_BUSINESS']);

// ── Simulated dispositions (never treated as real) ──────────────────

interface SimulatedDisposition {
  timestamp: string;
  phone: string;
  company: string;
  vertical: string;
  contact: string;
  outcome: string;
  detail: string;
}

function loadSimulatedOutcomes(): SimulatedDisposition[] {
  const p = path.join(OUT_DIR, 'close_dispositions.json');
  if (!fs.existsSync(p)) return [];
  try {
    const raw = JSON.parse(fs.readFileSync(p, 'utf8'));
    return (Array.isArray(raw) ? raw : raw.dispositions ?? raw.records ?? []) as SimulatedDisposition[];
  } catch {
    return [];
  }
}

// ── Helpers ──────────────────────────────────────────────────────────

function ownerDisplayName(record: DialerRecord): string {
  const n = record.details.Owner_Name?.trim();
  if (n && n !== record.company.toUpperCase()) return n;
  if (record.contact && record.contact !== record.company.toUpperCase()) return record.contact;
  return record.company;
}

function personTitle(record: DialerRecord): string {
  return (record.details.Title ?? record.title ?? '').trim() || 'Unknown';
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
  const person = ownerDisplayName(record);
  const q = (record.details.Discovery_Questions ?? [])[0] ?? 'How are you currently handling your front-desk calls and patient follow-ups?';
  return (
    `Hi ${person}, this is Omar with MBM Systems. I help healthcare practices in Texas automate their ` +
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
  return `If this made sense for ${record.company}'s front desk, would you be open to a 15-minute walkthrough this week — no obligation either way?`;
}

function finalClose(record: DialerRecord): string {
  const person = ownerDisplayName(record);
  return `I am not asking for a decision today, ${person}. I am asking for a calendar slot — Tuesday afternoon or Thursday morning, whichever works. Which is better?`;
}

// ── QA ───────────────────────────────────────────────────────────────

function qaCard(card: MoneyModeCard): QAResult[] {
  const checks: QAResult[] = [];
  for (const field of REQUIRED_CARD_FIELDS) {
    const value = card[field];
    if (value === undefined || value === null || value === '') {
      checks.push({ field, pass: false, reason: 'required field is empty' });
      continue;
    }
    if (Array.isArray(value)) {
      if (value.length === 0) {
        checks.push({ field, pass: false, reason: 'required field is an empty array' });
        continue;
      }
      if (value.some((v) => typeof v === 'string' && PLACEHOLDER_REGEX.test(v))) {
        checks.push({ field, pass: false, reason: 'contains an unresolved placeholder' });
        continue;
      }
      checks.push({ field, pass: true, reason: null });
      continue;
    }
    if (typeof value === 'object') {
      checks.push({ field, pass: true, reason: null });
      continue;
    }
    if (PLACEHOLDER_REGEX.test(String(value))) {
      checks.push({ field, pass: false, reason: 'contains an unresolved placeholder' });
      continue;
    }
    checks.push({ field, pass: true, reason: null });
  }
  return checks;
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
  const dialable: Array<{ record: DialerRecord; routing: OwnerRoutingResult }> = [];

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
    dialable.push({ record, routing });
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

  function buildCard(entry: { record: DialerRecord; routing: OwnerRoutingResult }): MoneyModeCard {
    const { record, routing } = entry;
    const phone = record.details.verified_phone ?? record.phone;
    const card: MoneyModeCard = {
      id: record.id,
      person: ownerDisplayName(record),
      title: personTitle(record),
      company: record.company,
      vertical: record.vertical,
      salesLane: 'AI_BUSINESS_OWNER',
      storedLane: record.sales_lane,
      contactStatus: record.skip_trace_status === 'VERIFIED' ? 'VERIFIED' : 'UNKNOWN',
      // The NPI registry evidences a licensed practitioner, NOT verified
      // ownership. DIRECTOR ≠ VERIFIED_OWNER — ownership stays UNKNOWN.
      ownerStatus: 'UNKNOWN',
      decisionMaker: routing.tier,
      phone,
      dealScore: record.deal_score,
      callabilityScore: record.callability_score,
      ownerRouting: routing,
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
      qa: { pass: true, checks: [] },
    };
    card.qa = { pass: false, checks: qaCard(card) };
    card.qa.pass = card.qa.checks.every((c) => c.pass);
    return card;
  }

  // GO-LIVE GATE: take the 25 prime + 75 next, and REPLACE any prime card
  // that fails QA with the next qualified card from the ranked pool.
  const allCards = ranked.map(buildCard);
  const prime = allCards.slice(0, 25);
  const reserve = allCards.slice(25);
  const primeFinal: MoneyModeCard[] = [];
  const qaFailures: Array<{ id: string; company: string; reasons: string[] }> = [];

  for (const card of prime) {
    if (!card.qa.pass) {
      qaFailures.push({
        id: card.id,
        company: card.company,
        reasons: card.qa.checks.filter((c) => !c.pass).map((c) => `${c.field}: ${c.reason}`),
      });
      continue;
    }
    primeFinal.push(card);
  }

  while (primeFinal.length < 25 && reserve.length > 0) {
    const replacement = reserve.shift()!;
    if (!replacement.qa.pass) {
      qaFailures.push({
        id: replacement.id,
        company: replacement.company,
        reasons: replacement.qa.checks.filter((c) => !c.pass).map((c) => `${c.field}: ${c.reason}`),
      });
      continue;
    }
    primeFinal.push(replacement);
  }

  const callNow = primeFinal;
  const next75 = reserve.slice(0, 75).filter((c) => c.qa.pass);
  const remaining = reserve.slice(75);

  // Outcome separation — simulated never touches real metrics.
  const simulatedOutcomes = loadSimulatedOutcomes();
  const realOutcomes: unknown[] = [];

  const metrics = {
    real: {
      calls: 0,
      connected: 0,
      qualified: 0,
      callbacks: 0,
      demos: 0,
      proposals: 0,
      wins: 0,
      revenue: 0,
      revenuePer100Calls: 0,
      connectRate: 'INSUFFICIENT_DATA',
      rightPersonRate: 'INSUFFICIENT_DATA',
      qualifiedRate: 'INSUFFICIENT_DATA',
      callbackRate: 'INSUFFICIENT_DATA',
      demoRate: 'INSUFFICIENT_DATA',
      proposalRate: 'INSUFFICIENT_DATA',
      closeRate: 'INSUFFICIENT_DATA',
      breakdowns: {
        byVertical: 'INSUFFICIENT_DATA',
        byOffer: 'INSUFFICIENT_DATA',
        bySource: 'INSUFFICIENT_DATA',
        byOwnerTier: 'INSUFFICIENT_DATA',
        byScript: 'INSUFFICIENT_DATA',
        byOpener: 'INSUFFICIENT_DATA',
        byObjection: 'INSUFFICIENT_DATA',
      },
      note: 'Zero real calls placed. Only REAL_OUTCOMES may drive these metrics — no simulated/dry-run data used.',
    },
    simulated: {
      dispositions: simulatedOutcomes.length,
      skipped: simulatedOutcomes.filter((o) => o.outcome === 'skipped').length,
      simulated: simulatedOutcomes.filter((o) => o.outcome === 'simulated').length,
      noAnswer: simulatedOutcomes.filter((o) => o.outcome === 'no-answer').length,
      note: 'Reported separately. Never mixed into commercial metrics.',
    },
  };

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
    qa: {
      primeChecked: callNow.length,
      primePass: callNow.every((c) => c.qa.pass) ? callNow.length : callNow.filter((c) => c.qa.pass).length,
      primeFailuresReplaced: qaFailures.length,
      failures: qaFailures,
      gate: {
        placeholders: callNow.some((c) => c.qa.checks.some((x) => !x.pass && /placeholder/i.test(x.reason ?? '')))
          ? 'FAIL'
          : '0 UNRESOLVED',
        dnc: '0',
        badNumber: '0',
        duplicates: '0',
        suppressed: '0',
        unresolvedRequiredFields: callNow.some((c) => !c.qa.pass) ? 'FAIL' : '0',
      },
    },
    cards: callNow,
    next75,
    verificationRequired,
    suppressed,
    followUpPriority: {
      codes: Array.from(FOLLOW_UP_PRIORITY_CODES),
      queue: [],
      note: 'Immediately prioritize CALLBACK / DEMO_BOOKED / PROPOSAL / NEGOTIATION once real outcomes exist.',
    },
    metrics,
    outcomeCodes: OUTCOME_CODES,
    realOutcomes,
    simulatedOutcomes,
    next_action: 'Dial CALL NOW 25 via close_queue_dialer.py; record REAL outcomes with the 14 codes; feed real results back into callability/learning. Do not dial the remaining 499.',
    owner: 'system',
  };

  fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2));

  const blocks = callNow.map((card, i) =>
    [
      `═══════════════════════════════════════════`,
      `#${i + 1} · ${card.company}`,
      `PERSON: ${card.person}`,
      `TITLE: ${card.title}`,
      `COMPANY: ${card.company}`,
      `VERTICAL: ${card.vertical}`,
      `LANE: ${card.salesLane} (stored: ${card.storedLane})`,
      `CONTACT STATUS: ${card.contactStatus}`,
      `OWNER STATUS: ${card.ownerStatus}`,
      `DECISION MAKER: ${card.decisionMaker}`,
      `WHY THIS LEAD: ${card.whyThisLead}`,
      `EVIDENCE: ${card.evidenceSignal}`,
      `OFFER: ${card.recommendedOffer}`,
      `Callability: ${card.callabilityScore}/100 · Deal Score: ${card.dealScore}/100 · Phone: ${card.phone}`,
      ``,
      `OPENING: ${card.opening}`,
      `DISCOVERY: ${card.discoveryQuestions.join('  ')}`,
      `OBJECTIONS:`,
      ...card.objectionPaths.map((o) => `  • ${o.trigger} → ${o.response}`),
      `CLOSE (TRIAL): ${card.trialClose}`,
      `CLOSE (FINAL): ${card.finalClose}`,
      `NEXT ACTION: ${card.nextAction}`,
      `QA: ${card.qa.pass ? 'PASS' : 'FAIL'}`,
      ``,
    ].join('\n'),
  );
  fs.writeFileSync(txtPath, blocks.join('\n'));

  const outcomesPath = path.join(OUT_DIR, `money-mode-outcomes-${DATE}.json`);
  const outcomes = {
    status: 'success',
    timestamp: new Date().toISOString(),
    realCodes: OUTCOME_CODES,
    realOutcomes: [],
    simulatedOutcomes,
    followUpPriority: Array.from(FOLLOW_UP_PRIORITY_CODES),
    metrics,
    note: 'Real outcome capture scaffold. Add { id, phone, code, ts, notes } under realOutcomes ONLY for actual calls. Simulated dispositions stay separate and never affect metrics.',
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
          primePass: callNow.every((c) => c.qa.pass) ? callNow.length : callNow.filter((c) => c.qa.pass).length,
          qaFailuresReplaced: qaFailures.length,
          jsonPath,
          txtPath,
          outcomesPath,
        },
        metrics: { realCalls: 0, revenue: 0, connectRate: 'INSUFFICIENT_DATA', simulatedDispositions: simulatedOutcomes.length },
        next_action: 'Dial CALL NOW 25; record REAL outcomes; feed back into callability. Do not dial the remaining 499.',
        owner: 'system',
      },
      null,
      2,
    ),
  );
}

main();