# Supabase Deployment Checklist — AD Engine Tables

## Pre-Deployment

- [ ] **Backup database** before migration: `supabase db dump > backup_$(date +%Y%m%d).sql`
- [ ] **Verify migration is additive only** — no existing tables modified, no destructive drops
- [ ] **Review migration**: `supabase/migrations/00017_ad_engine_tables.sql`
  - 9 new tables: buyer_buy_boxes, deal_submissions, social_interactions, next_best_actions, follow_ups, demand_signals, revenue_events, audit_log_entries
  - Composite unique: `demand_signals(market, property_type, price_band)`
  - CHECK constraints on revenue_events, follow_ups, next_best_actions, deal_submissions
  - Auto-update triggers for `updated_at` on 4 tables
  - 30+ indexes for query performance

## Deploy

```bash
# Option 1: supabase CLI (recommended)
supabase db push

# Option 2: Direct SQL via Supabase Dashboard
# Copy contents of 00017_ad_engine_tables.sql into SQL Editor and run

# Verify
supabase db diff --schema public
```

## Post-Deployment Verification

```sql
-- 1. Check all tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('buyer_buy_boxes','deal_submissions','social_interactions',
                    'next_best_actions','follow_ups','demand_signals',
                    'revenue_events','audit_log_entries');

-- 2. Verify CHECK constraints
SELECT conname, contype FROM pg_constraint
WHERE conrelid IN (
    'revenue_events'::regclass,
    'follow_ups'::regclass,
    'next_best_actions'::regclass,
    'deal_submissions'::regclass
);

-- 3. Verify triggers exist
SELECT trigger_name, event_object_table FROM information_schema.triggers
WHERE trigger_name LIKE 'trg_%_updated';

-- 4. Verify indexes
SELECT indexname FROM pg_indexes
WHERE tablename IN ('buyer_buy_boxes','deal_submissions','social_interactions',
                    'next_best_actions','follow_ups','demand_signals',
                    'revenue_events','audit_log_entries')
AND indexname LIKE 'idx_%';

-- 5. Test insert (should succeed)
INSERT INTO buyer_buy_boxes (buyer_id, buyer_name) VALUES ('TEST_001', 'Test Buyer');
DELETE FROM buyer_buy_boxes WHERE buyer_id = 'TEST_001';

-- 6. Verify CHECK constraint (should fail with invalid status)
INSERT INTO deal_submissions (address, city, state) VALUES ('123 Test', 'Dallas', 'TX');
-- Then: UPDATE deal_submissions SET status = 'INVALID_STATUS' WHERE address = '123 Test';
-- Should fail with CHECK constraint violation
```

## Environment Configuration

```bash
# Set these in production environment:
AD_ENV=PRODUCTION          # or MBM_ENV=PRODUCTION
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Verify repository connects
python -c "from MBM.LeadEngine.ad_repository import AdRepository; r = AdRepository()"
# Should log: "AD Repository: PRODUCTION mode (Supabase)"
# If Supabase unavailable, should raise RuntimeError (fail-closed)
```

## Rollback Plan

Migration 00017 is additive only — no existing data is modified. To rollback:

```sql
-- Drop new tables (safe — no existing tables affected)
DROP TABLE IF EXISTS audit_log_entries CASCADE;
DROP TABLE IF EXISTS revenue_events CASCADE;
DROP TABLE IF EXISTS demand_signals CASCADE;
DROP TABLE IF EXISTS follow_ups CASCADE;
DROP TABLE IF EXISTS next_best_actions CASCADE;
DROP TABLE IF EXISTS social_interactions CASCADE;
DROP TABLE IF EXISTS deal_submissions CASCADE;
DROP TABLE IF EXISTS buyer_buy_boxes CASCADE;

-- Drop trigger function (only if not used elsewhere)
DROP FUNCTION IF EXISTS update_updated_at();
```

## Known Limitations

- **No foreign keys**: Tables use TEXT IDs (not UUID FKs) for flexibility across JSON/Supabase.
  - `revenue_events.deal_id` → `deal_submissions.id` (logical, not enforced)
  - `next_best_actions.entity_id` → various tables (polymorphic)
- **demand_signals upsert**: Uses `on_conflict="market,property_type,price_band"` — requires the composite unique constraint
- **Revenue events are immutable**: No UPDATE/DELETE at the DB level (enforced by application logic, not DB constraints)
- **Audit log is append-only**: No UPDATE/DELETE (application-level enforcement)
