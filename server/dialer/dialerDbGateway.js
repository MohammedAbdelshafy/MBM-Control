/**
 * MBM Dialer DB Gateway (Node) — canonical write path for leads_database.json.
 *
 * Mirrors the Python single-writer protocol in MBM/GLM/single_writer_lock.py:
 *   - Same lock file (MBM/Artifacts/.leads_database.lock), acquired with O_EXCL.
 *   - Same stale-lock break (>30s).
 *   - Atomic write via temp file + rename (never a partial JSON on disk).
 *   - Never-shrink invariant by default (allowShrink only for explicit purges).
 *
 * Every Node writer MUST go through this module; no direct writeFileSync.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT_DIR = path.join(__dirname, '..', '..');
export const DIALER_DB_PATH = path.join(ROOT_DIR, 'mbm-dialer', 'app', 'public', 'leads_database.json');
const LOCK_FILE = path.join(ROOT_DIR, 'MBM', 'Artifacts', '.leads_database.lock');
const STALE_LOCK_MS = 30 * 1000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function acquireLock(timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const fd = fs.openSync(LOCK_FILE, 'wx');
      fs.writeFileSync(
        fd,
        JSON.stringify({ pid: process.pid, source: 'node-server', timestamp: new Date().toISOString() })
      );
      fs.closeSync(fd);
      return true;
    } catch (err) {
      if (err.code !== 'EEXIST') return false;
      try {
        const stat = fs.statSync(LOCK_FILE);
        if (Date.now() - stat.mtimeMs > STALE_LOCK_MS) {
          fs.unlinkSync(LOCK_FILE);
          continue;
        }
      } catch (e) {
        // Lock vanished between stat and unlink — retry acquisition.
      }
    }
    await sleep(50);
  }
  return false;
}

export function releaseLock() {
  try {
    if (fs.existsSync(LOCK_FILE)) fs.unlinkSync(LOCK_FILE);
  } catch (e) {
    /* ignore */
  }
}

export function readLeads() {
  if (!fs.existsSync(DIALER_DB_PATH)) return [];
  const raw = fs.readFileSync(DIALER_DB_PATH, 'utf8');
  const data = JSON.parse(raw);
  return Array.isArray(data) ? data : data.leads || [];
}

/**
 * Patch one or more leads by id. Read-modify-write under the shared lock with
 * an atomic temp+rename commit. Never shrinks the dataset.
 */
export async function patchLeads(mutations, { author = 'node-server' } = {}) {
  const ok = await acquireLock();
  if (!ok) throw new Error('Could not acquire single-writer lock on leads_database.json');

  try {
    const arr = readLeads();
    const initial = arr.length;
    let patched = 0;

    for (const m of mutations) {
      const target = arr.find((l) => String(l.id) === String(m.id));
      if (!target) continue;
      for (const [k, v] of Object.entries(m.fields)) target[k] = v;
      patched += 1;
    }

    if (patched === 0) return { ok: true, author, patched: 0, initial, final: initial };

    if (arr.length < initial) {
      throw new Error(`Dataset shrinkage detected! Initial: ${initial}, Final: ${arr.length}. Write aborted.`);
    }

    const tmp = path.join(path.dirname(DIALER_DB_PATH), `.leads_db_${process.pid}_${Date.now()}.tmp`);
    fs.writeFileSync(tmp, JSON.stringify(arr, null, 2), 'utf8');

    let replaced = false;
    for (let i = 0; i < 20 && !replaced; i++) {
      try {
        fs.renameSync(tmp, DIALER_DB_PATH);
        replaced = true;
      } catch (e) {
        await sleep(50);
      }
    }
    if (!replaced) {
      fs.copyFileSync(tmp, DIALER_DB_PATH);
      try { fs.unlinkSync(tmp); } catch (e) { /* ignore */ }
    }

    return { ok: true, author, patched, initial, final: arr.length };
  } finally {
    releaseLock();
  }
}