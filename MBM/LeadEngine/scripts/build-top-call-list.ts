/**
 * Build the REAL Top-N call list from the NPI clinic lead database.
 *
 * Reads `mbm-dialer/app/public/leads_database.json` (real CMS NPI Registry
 * businesses), maps them through the vertical engine, ranks by buying
 * probability, and writes:
 *   logs/top-call-list-<date>.json   — full records + mapper + rank report
 *   logs/top-call-list-<date>.csv    — call-ready rows for the dialer
 *
 * Honesty: NPI supplies identity/contact only. Digital-gap, buying, and
 * automation signals are NOT evincable from this source and are never
 * asserted; the ranking reflects contact certainty + vertical baseline.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import {
  VerticalRegistry,
  mapNpiLeads,
  rankOpportunities,
} from '../src/verticals';
import type { NpiClinicRecord, TopCallRecord } from '../src/verticals';

const DATA_PATH = path.resolve(__dirname, '..', '..', '..', 'mbm-dialer', 'app', 'public', 'leads_database.json');
const OUT_DIR = path.resolve(__dirname, '..', 'logs');
const limit = Number(process.env.TOP_N ?? '100');
const minBuyingProbability = Number(process.env.MIN_BUYING_PROBABILITY ?? '0');

function main(): void {
  if (!fs.existsSync(DATA_PATH)) {
    console.error(`status: failure — leads database not found at ${DATA_PATH}`);
    process.exit(1);
  }

  const raw = JSON.parse(fs.readFileSync(DATA_PATH, 'utf8')) as NpiClinicRecord[];
  const { results, report } = mapNpiLeads(raw);

  const registry = new VerticalRegistry();
  const resolved = results.map((r) => ({
    vertical: registry.require(r.verticalId),
    evidence: r.evidence,
  }));
  const top = rankOpportunities(resolved, { minBuyingProbability, requireContactPath: true }).slice(0, limit);

  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  const today = new Date().toISOString().slice(0, 10);
  const jsonPath = path.join(OUT_DIR, `top-call-list-${today}.json`);
  const csvPath = path.join(OUT_DIR, `top-call-list-${today}.csv`);

  const payload = {
    status: 'success',
    timestamp: new Date().toISOString(),
    inputs: { limit, minBuyingProbability, source: DATA_PATH },
    mapperReport: report,
    ranked: top.map((r) => ({
      verticalId: r.vertical.id,
      verticalName: r.vertical.name,
      evidence: r.evidence,
      opportunity: r.opportunity,
    })),
  };
  fs.writeFileSync(jsonPath, JSON.stringify(payload, null, 2));

  const header = [
    'rank', 'company', 'vertical', 'industry', 'npi', 'city', 'state', 'phone',
    'decision_maker', 'decision_maker_title', 'buying_probability',
    'contactability_score', 'lead_score', 'recommended_offer', 'outreach_angle',
    'why_now', 'provenance',
  ];
  const rows = top.map((r, i) => {
    const o: TopCallRecord = r.opportunity;
    const npi = (r.evidence.extra?.npi as string) ?? '';
    const dm = r.evidence.decisionMaker;
    return [
      i + 1,
      csv(r.evidence.company),
      r.vertical.id,
      csv(r.evidence.industry ?? ''),
      npi,
      csv(r.evidence.location?.city ?? ''),
      csv(r.evidence.location?.state ?? ''),
      csv(o.contact.phone ?? ''),
      csv(dm?.name ?? ''),
      csv(dm?.title ?? ''),
      Math.round(o.buyingProbability),
      Math.round(o.contactabilityScore),
      Math.round(o.leadScore),
      csv(o.recommendedOffer),
      csv(o.bestOutreachAngle),
      csv(o.whyNow),
      csv(r.evidence.source),
    ];
  });
  fs.writeFileSync(csvPath, [header.join(','), ...rows.map((r) => r.join(','))].join('\n'));

  console.log(JSON.stringify({
    status: 'success',
    timestamp: new Date().toISOString(),
    inputs: { limit, minBuyingProbability, source: DATA_PATH },
    outputs: {
      mappedRecords: report.mappedCount,
      skippedUnmapped: report.skippedUnmappedCount,
      skippedNoPhone: report.skippedNoPhoneCount,
      verticalCounts: report.verticalCounts,
      topListSize: top.length,
      jsonPath,
      csvPath,
      topEntry: top[0]
        ? { rank: 1, company: top[0].evidence.company, vertical: top[0].vertical.id, buyingProbability: Math.round(top[0].opportunity.buyingProbability) }
        : null,
    },
    next_action: 'review logs/top-call-list-*.json and hand the CSV to the dialer queue',
    owner: 'system',
  }, null, 2));
}

function csv(v: string): string {
  const s = String(v ?? '');
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

main();