// Canonical dialer queue ordering. SINGLE ordering source for the API layer.
// The backend engine (MBM/LeadEngine/dialer_queue_engine.py) writes
// leads_database.json in freshness-first order. This comparator applies the
// same rule as a safety net; full ties return 0 so the (stable) JS sort keeps
// the engine's stored order verbatim — guaranteeing API order == DB order.
//
// Order (first differing key decides):
//   1. queue_bucket        FRESH_CALL_NOW → FRESH_NEXT → UNCALLED_VERIFIED →
//                          ALREADY_CONTACTED → VERIFICATION_REQUIRED →
//                          SUPPRESSED → QUARANTINED
//   2. freshness_stage     NEWLY_IMPORTED → NEWLY_VERIFIED → NEWLY_ENRICHED → OLD
//   3. priority_score      DESC
//   4. freshness_score     DESC
//   5. distress_score      DESC
//   (full ties keep stored order)

export const QUEUE_BUCKET_RANK = {
  FRESH_CALL_NOW: 0,
  FRESH_NEXT: 1,
  UNCALLED_VERIFIED: 2,
  ALREADY_CONTACTED: 3,
  VERIFICATION_REQUIRED: 4,
  SUPPRESSED: 5,
  QUARANTINED: 6,
};

export const FRESHNESS_STAGE_RANK = {
  NEWLY_IMPORTED: 0,
  NEWLY_VERIFIED: 1,
  NEWLY_ENRICHED: 2,
  OLD: 3,
};

// Legacy/unranked leads sink to the tail of each tier so they never jump
// ahead of a lead whose bucket/stage was explicitly stamped by the engine.
const DEFAULT_BUCKET_RANK = 3;
const DEFAULT_STAGE_RANK = 3;

function toInt(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

export function compareDialerLeads(a, b) {
  const bucketA = QUEUE_BUCKET_RANK[a.queue_bucket] ?? DEFAULT_BUCKET_RANK;
  const bucketB = QUEUE_BUCKET_RANK[b.queue_bucket] ?? DEFAULT_BUCKET_RANK;
  if (bucketA !== bucketB) return bucketA - bucketB;

  const freshA = FRESHNESS_STAGE_RANK[a.freshness_stage] ?? DEFAULT_STAGE_RANK;
  const freshB = FRESHNESS_STAGE_RANK[b.freshness_stage] ?? DEFAULT_STAGE_RANK;
  if (freshA !== freshB) return freshA - freshB;

  const prioA = toInt(a.priority_score);
  const prioB = toInt(b.priority_score);
  if (prioA !== prioB) return prioB - prioA;

  const fsA = toInt(a.freshness_score);
  const fsB = toInt(b.freshness_score);
  if (fsA !== fsB) return fsB - fsA;

  const distA = toInt(a.distress_score);
  const distB = toInt(b.distress_score);
  if (distA !== distB) return distB - distA;

  return 0;
}