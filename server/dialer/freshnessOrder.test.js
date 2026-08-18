// Canonical dialer ordering tests — the controlled case that triggered the fix:
//   NEW_A(fresh, prio 80), NEW_B(fresh, prio 70), OLD_A(old, prio 99)
// must order NEW_A, NEW_B, OLD_A — freshness dominates raw score.
import assert from 'node:assert/strict';
import {
  compareDialerLeads,
  QUEUE_BUCKET_RANK,
  FRESHNESS_STAGE_RANK,
} from './freshnessOrder.js';

const lead = (overrides = {}) => ({
  id: 'X',
  queue_bucket: 'FRESH_CALL_NOW',
  freshness_stage: 'NEWLY_IMPORTED',
  priority_score: 80,
  freshness_score: 95,
  distress_score: 80,
  ...overrides,
});

const sortIds = (arr) => [...arr].sort(compareDialerLeads).map((l) => l.id);

// ── Controlled case: freshness outranks higher raw scores ──────────────────
{
  const newA = lead({ id: 'NEW_A', priority_score: 80 });
  const newB = lead({ id: 'NEW_B', priority_score: 70 });
  const oldA = lead({ id: 'OLD_A', priority_score: 99, freshness_stage: 'OLD', freshness_score: 25 });
  assert.deepEqual(sortIds([oldA, newB, newA]), ['NEW_A', 'NEW_B', 'OLD_A']);
}

// ── Bucket dominates everything below it ────────────────────────────────────
{
  const callNow = lead({ id: 'CALL_NOW_50', priority_score: 50 });
  const next100 = lead({ id: 'NEXT_100', queue_bucket: 'FRESH_NEXT', priority_score: 100 });
  const uncalled99 = lead({ id: 'UNCALLED_99', queue_bucket: 'UNCALLED_VERIFIED', freshness_stage: 'NEWLY_IMPORTED', priority_score: 99 });
  assert.deepEqual(sortIds([uncalled99, next100, callNow]), ['CALL_NOW_50', 'NEXT_100', 'UNCALLED_99']);
}

// ── Fresh 82 beats old 99 when both callable (same bucket) ─────────────────
{
  const fresh82 = lead({ id: 'FRESH_82', priority_score: 82, freshness_stage: 'NEWLY_IMPORTED' });
  const old99 = lead({ id: 'OLD_99', priority_score: 99, freshness_stage: 'OLD', freshness_score: 25 });
  assert.deepEqual(sortIds([old99, fresh82]), ['FRESH_82', 'OLD_99']);
}

// ── Stage rank order inside a bucket ────────────────────────────────────────
{
  const imported = lead({ id: 'IMPORTED', freshness_stage: 'NEWLY_IMPORTED', priority_score: 60 });
  const verified = lead({ id: 'VERIFIED', freshness_stage: 'NEWLY_VERIFIED', priority_score: 90 });
  const enriched = lead({ id: 'ENRICHED', freshness_stage: 'NEWLY_ENRICHED', priority_score: 95 });
  const old = lead({ id: 'OLD', freshness_stage: 'OLD', priority_score: 99, freshness_score: 25 });
  assert.deepEqual(sortIds([old, enriched, verified, imported]), ['IMPORTED', 'VERIFIED', 'ENRICHED', 'OLD']);
}

// ── priority_score DESC within same bucket+stage ────────────────────────────
{
  const a = lead({ id: 'P_60', priority_score: 60 });
  const b = lead({ id: 'P_90', priority_score: 90 });
  const c = lead({ id: 'P_90_B', priority_score: 90 });
  assert.deepEqual(sortIds([a, b, c]), ['P_90', 'P_90_B', 'P_60']);
}

// ── freshness_score DESC within same bucket+stage+priority ─────────────────
{
  const f70 = lead({ id: 'F_70', freshness_score: 70 });
  const f95 = lead({ id: 'F_95', freshness_score: 95 });
  assert.deepEqual(sortIds([f70, f95]), ['F_95', 'F_70']);
}

// ── distress_score DESC final numeric tiebreak ──────────────────────────────
{
  const d50 = lead({ id: 'D_50', priority_score: 70, freshness_score: 95, distress_score: 50 });
  const d90 = lead({ id: 'D_90', priority_score: 70, freshness_score: 95, distress_score: 90 });
  assert.deepEqual(sortIds([d50, d90]), ['D_90', 'D_50']);
}

// ── Full ties are stable: stored (engine) order is preserved ───────────────
{
  const a = lead({ id: 'A' });
  const b = lead({ id: 'B' });
  const c = lead({ id: 'C' });
  assert.deepEqual(sortIds([c, a, b]), ['C', 'A', 'B']);
}

// ── Legacy records with no metadata sink to their tier tail, never ahead ───
{
  const legacy = lead({ id: 'LEGACY', queue_bucket: '', freshness_stage: '', priority_score: 0 });
  const stamped = lead({ id: 'STAMPED', queue_bucket: 'FRESH_CALL_NOW', freshness_stage: 'NEWLY_IMPORTED', priority_score: 10 });
  assert.deepEqual(sortIds([legacy, stamped]), ['STAMPED', 'LEGACY']);
}

// ── Ranks are exported for reuse/UI parity ─────────────────────────────────
assert.equal(QUEUE_BUCKET_RANK.FRESH_CALL_NOW, 0);
assert.equal(QUEUE_BUCKET_RANK.QUARANTINED, 6);
assert.equal(FRESHNESS_STAGE_RANK.NEWLY_IMPORTED, 0);
assert.equal(FRESHNESS_STAGE_RANK.OLD, 3);

console.log('freshnessOrder.test.js: all assertions passed');