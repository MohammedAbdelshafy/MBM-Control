#!/usr/bin/env node
/**
 * HUNTER — Hourly revenue outreach CLI.
 *
 * Queues new targets to the Supabase email_queue via clientHunter.hunt(),
 * then drains the queue via sendEmailQueue(). Idempotent: skips targets
 * that were already contacted.
 *
 * Usage:
 *   node server/hunterSend.js --dry-run            # preview what would be queued
 *   node server/hunterSend.js --send               # queue new targets + drain email queue
 *   node server/hunterSend.js --send --limit 10    # process at most N targets
 *   node server/hunterSend.js --daemon             # loop every hour (send + drain)
 */
import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });
import { createClient } from '@supabase/supabase-js';
import { hunt } from './clientHunter.js';
import { sendEmailQueue } from './emailSender.js';

const HOUR_MS = 60 * 60 * 1000;

function getSupabase() {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) throw new Error('SUPABASE_SERVICE_ROLE_KEY required in .env.local');
  return createClient(
    process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co',
    key,
  );
}

async function runCycle({ dryRun = false, limit = 0 } = {}) {
  const supabase = dryRun ? undefined : getSupabase();
  const result = await hunt({ supabase, dryRun, limit });
  console.log(`\n=== HUNTER ${dryRun ? 'DRY RUN' : 'OUTREACH'} ===`);
  console.log(`Queued: ${result.queued} | Skipped: ${result.skipped} | Bounced: ${result.bounced} | Total targets: ${result.total}`);

  if (result.queued > 0 && !dryRun) {
    console.log('\nDraining email queue...');
    const sendResult = await sendEmailQueue({ supabase, batchSize: 5000, continuous: false });
    console.log(`Send result: ${JSON.stringify(sendResult)}`);
  }
  return result;
}

async function main() {
  const args = process.argv.slice(2);
  const limitIdx = args.indexOf('--limit');
  const limit = limitIdx >= 0 ? parseInt(args[limitIdx + 1], 10) || 0 : 0;

  if (args.includes('--daemon')) {
    console.log('[HUNTER] Daemon started — running every hour (:30 sync with server cron)');
    // eslint-disable-next-line no-constant-condition
    while (true) {
      try {
        await runCycle({ dryRun: false, limit });
      } catch (err) {
        console.error('[HUNTER] cycle error:', err.message);
      }
      await new Promise(r => setTimeout(r, HOUR_MS));
    }
  }

  await runCycle({
    dryRun: args.includes('--dry-run'),
    limit,
  });
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
