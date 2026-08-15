/**
 * Build ONE-SCREEN DIALER CARDS from the top-call list.
 *
 * Reads the latest `logs/top-call-list-<date>.json` (real, provenance-backed
 * opportunities from the vertical engine), owner-first sorts the records,
 * renders the full dynamic script + objection branch + dialer payload for
 * each, and writes:
 *   logs/dialer-cards-<date>.json   — full card payloads (dialer-ready)
 *   logs/dialer-cards-<date>.txt    — human-readable one-screen cards
 *
 * The caller needs NO separate research screen: each card carries owner,
 * company, vertical, why-this-lead, recommended offer, opener, discovery,
 * objection, close, callability and lead score.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import {
  VerticalRegistry,
  ownerFirstSort,
  buildDialerPayload,
} from '../src/verticals';
import type { TopCallRecord } from '../src/verticals';

const OUT_DIR = path.resolve(__dirname, '..', 'logs');
const limit = Number(process.env.CARDS_LIMIT ?? '50');
const maxCards = Math.max(1, Math.min(limit, 500));

function findLatestTopCallList(): string {
  const files = fs
    .readdirSync(OUT_DIR)
    .filter((f) => /^top-call-list-\d{4}-\d{2}-\d{2}\.json$/.test(f))
    .sort();
  if (files.length === 0) {
    throw new Error('No top-call-list-*.json found in logs/ — run build-top-call-list first.');
  }
  return path.join(OUT_DIR, files[files.length - 1]);
}

function main(): void {
  const sourcePath = process.env.TOP_CALL_LIST_PATH || findLatestTopCallList();
  if (!fs.existsSync(sourcePath)) {
    console.error(`status: failure — top call list not found at ${sourcePath}`);
    process.exit(1);
  }

  const parsed = JSON.parse(fs.readFileSync(sourcePath, 'utf8')) as {
    ranked?: Array<{
      verticalId: string;
      verticalName: string;
      evidence: unknown;
      opportunity: TopCallRecord;
    }>;
  };
  const ranked = parsed.ranked ?? [];
  if (ranked.length === 0) {
    console.error('status: failure — top call list contains no ranked records');
    process.exit(1);
  }

  const registry = new VerticalRegistry();
  const records = ranked
    .filter((r) => registry.get(r.verticalId))
    .map((r) => ({
      vertical: registry.require(r.verticalId),
      evidence: r.evidence,
      opportunity: r.opportunity,
    }));

  // Owner-first: qualified decision makers rise to the top of the dialer.
  const ownerSorted = ownerFirstSort(records.map((r) => r.opportunity)).slice(0, maxCards);
  const byCompany = new Map(
    records.map((r) => [r.opportunity.company.toLowerCase(), r]),
  );

  const cards = ownerSorted.map((op) => {
    const record = byCompany.get(op.company.toLowerCase());
    const payload = buildDialerPayload({
      vertical: record!.vertical,
      opportunity: op,
      evidence: record!.evidence,
    });
    return { ...payload, rank: op.buyingProbability };
  });

  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });
  const today = new Date().toISOString().slice(0, 10);
  const jsonPath = path.join(OUT_DIR, `dialer-cards-${today}.json`);
  const txtPath = path.join(OUT_DIR, `dialer-cards-${today}.txt`);

  fs.writeFileSync(
    jsonPath,
    JSON.stringify(
      { status: 'success', timestamp: new Date().toISOString(), inputs: { sourcePath, maxCards }, cards },
      null,
      2,
    ),
  );

  const blocks = cards.map((card, i) =>
    [
      `═══════════════════════════════════════════`,
      `#${i + 1} · ${card.ownerRouting.routeLabel} · ${card.company}`,
      `Vertical: ${card.vertical} · ${card.ownerRouting.ownerName ?? 'owner'}`,
      `Callability: ${card.callability}/100 · Lead Score: ${card.leadScore}/100`,
      ``,
      `WHY THIS LEAD: ${card.whyThisLead}`,
      `RECOMMENDED OFFER: ${card.recommendedOffer}`,
      ``,
      `OPENER: ${card.opener}`,
      `DISCOVERY: ${card.discovery}`,
      `OBJECTION: ${card.objection}`,
      `CLOSE: ${card.close}`,
      ``,
    ].join('\n'),
  );
  fs.writeFileSync(txtPath, blocks.join('\n'));

  console.log(JSON.stringify({
    status: 'success',
    timestamp: new Date().toISOString(),
    inputs: { sourcePath, maxCards },
    outputs: {
      cardsBuilt: cards.length,
      jsonPath,
      txtPath,
      ownerFirstCount: cards.filter((c) => c.ownerRouting.isDecisionMaker).length,
      topCard: cards[0]
        ? { rank: 1, company: cards[0].company, vertical: cards[0].verticalId, owner: cards[0].owner }
        : null,
    },
    next_action: 'hand logs/dialer-cards-*.json to the dialer queue; caller reads one card per call',
    owner: 'system',
  }, null, 2));
}

main();