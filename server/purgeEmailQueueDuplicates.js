import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });
import { createClient } from '@supabase/supabase-js';
import fs from 'fs';
import path from 'path';

const supabase = createClient(process.env.VITE_SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);

const dryRun = process.argv.includes('--dry-run');
const backupOnly = process.argv.includes('--backup-only');
const fromBackupArg = process.argv.indexOf('--from-backup');
const fromBackup = fromBackupArg > -1 ? process.argv[fromBackupArg + 1] : null;
const PAGE = 1000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function retry(fn, label, attempts = 8) {
  let lastErr;
  for (let i = 1; i <= attempts; i++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      const wait = 2000 * i + Math.floor(Math.random() * 1000);
      console.log(`  ${label} attempt ${i} failed (${err.message}); retrying in ${wait / 1000}s`);
      await sleep(wait);
    }
  }
  throw lastErr;
}

function key(row) {
  return `${(row.recipient_email || '').trim().toLowerCase()}|${(row.subject || '').trim().toLowerCase()}`;
}

async function fetchAllQueued() {
  const rows = [];
  let lastId = '00000000-0000-0000-0000-000000000000';
  while (true) {
    const { data, error } = await retry(async () => {
      const r = await supabase
        .from('email_queue')
        .select('id, recipient_email, subject, created_at')
        .eq('status', 'qued')
        .gt('id', lastId)
        .order('id', { ascending: true })
        .limit(PAGE);
      if (r.error) throw new Error(`fetch page error: ${r.error.message}`);
      return r;
    }, 'fetch');
    rows.push(...data);
    if (data.length < PAGE) break;
    lastId = data[data.length - 1].id;
    console.log(`  fetched ${rows.length} rows...`);
  }
  return rows;
}

function computeDupes(rows) {
  const seen = new Set();
  const toDelete = [];
  const keep = [];
  for (const row of rows) {
    const k = key(row);
    if (seen.has(k)) toDelete.push(row.id);
    else {
      seen.add(k);
      keep.push(row);
    }
  }
  return { toDelete, keep };
}

async function main() {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backupPath = path.join('MBM', 'Artifacts', `email_queue_qued_backup_${stamp}.json`);

  console.log(`[purge] dry-run=${dryRun} backup-only=${backupOnly} from-backup=${fromBackup || 'none'}`);

  let rows;
  if (fromBackup) {
    rows = JSON.parse(fs.readFileSync(fromBackup, 'utf8'));
    console.log(`[purge] loaded ${rows.length} rows from backup: ${fromBackup}`);
  } else {
    console.log('[purge] fetching all "qued" rows...');
    rows = await fetchAllQueued();
    console.log(`[purge] total qued rows: ${rows.length}`);
    fs.mkdirSync(path.dirname(backupPath), { recursive: true });
    fs.writeFileSync(backupPath, JSON.stringify(rows, null, 2));
    console.log(`[purge] backup written: ${backupPath}`);
  }

  if (backupOnly) {
    console.log('[purge] --backup-only, exiting');
    return;
  }

  const { toDelete, keep } = computeDupes(rows);

  console.log(`[purge] unique (email|subject): ${keep.length}`);
  console.log(`[purge] duplicates to delete:   ${toDelete.length}`);

  if (dryRun) {
    console.log('[purge] --dry-run, no deletes performed');
    return;
  }

  const CHUNK = 200;
  let done = 0;
  for (let i = 0; i < toDelete.length; i += CHUNK) {
    const chunk = toDelete.slice(i, i + CHUNK);
    await retry(async () => {
      const { error } = await supabase.from('email_queue').delete().in('id', chunk);
      if (error) throw new Error(`delete chunk ${i} failed: ${error.message}`);
    }, `delete ${i}`);
    done += chunk.length;
    if (done % 10000 === 0 || done === toDelete.length) console.log(`[purge] deleted ${done}/${toDelete.length}`);
  }
  console.log(`[purge] done. deleted ${done}/${toDelete.length}`);
}

main().catch((e) => {
  console.error('[purge] FATAL:', e);
  process.exit(1);
});
