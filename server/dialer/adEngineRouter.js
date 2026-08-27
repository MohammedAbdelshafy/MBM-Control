/**
 * MBM AD Engine API Router
 * =========================
 * Express router exposing the Acquisition-Disposition engine
 * to the React frontend. All endpoints call the Python AdService
 * via child_process.spawn to avoid cross-language import issues.
 *
 * Pattern: Node Express → Python CLI → JSON stdout → parse → respond
 */

import express from 'express';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.join(__dirname, '..', '..');
const PYTHON = path.join(ROOT_DIR, '.venv', 'Scripts', 'python.exe');
const PYTHON_FALLBACK = 'python';

const router = express.Router();

function runPython(script, args = [], timeout = 30000) {
  return new Promise((resolve, reject) => {
    const python = PYTHON;
    const proc = spawn(python, ['-m', script, ...args], {
      cwd: ROOT_DIR,
      timeout,
      env: { ...process.env, PYTHONPATH: ROOT_DIR },
    });

    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', d => { stdout += d.toString(); });
    proc.stderr.on('data', d => { stderr += d.toString(); });
    proc.on('close', code => {
      if (code !== 0) {
        reject(new Error(`Python exited ${code}: ${stderr.slice(0, 500)}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        resolve({ raw: stdout.trim(), stderr: stderr.trim() });
      }
    });
    proc.on('error', reject);
  });
}

function runPythonDirect(scriptPath, args = [], timeout = 30000) {
  return new Promise((resolve, reject) => {
    const python = PYTHON;
    const fullPath = path.join(ROOT_DIR, ...scriptPath.split('/'));
    const proc = spawn(python, [fullPath, ...args], {
      cwd: ROOT_DIR,
      timeout,
      env: { ...process.env, PYTHONPATH: ROOT_DIR },
    });

    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', d => { stdout += d.toString(); });
    proc.stderr.on('data', d => { stderr += d.toString(); });
    proc.on('close', code => {
      if (code !== 0) {
        reject(new Error(`Python exited ${code}: ${stderr.slice(0, 500)}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        resolve({ raw: stdout.trim(), stderr: stderr.trim() });
      }
    });
    proc.on('error', reject);
  });
}

// ─── PIPELINE ────────────────────────────────────────────────────

router.get('/ad/snapshot', async (req, res) => {
  try {
    const data = await runPython('MBM.LeadEngine.ad_orchestrator', ['snapshot']);
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.get('/ad/demand', async (req, res) => {
  try {
    const data = await runPython('MBM.LeadEngine.ad_orchestrator', ['demand']);
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.get('/ad/disposition-view', async (req, res) => {
  try {
    const data = await runPython('MBM.LeadEngine.ad_orchestrator', ['disposition']);
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.get('/ad/today', async (req, res) => {
  try {
    const data = await runPython('MBM.LeadEngine.ad_orchestrator', ['today']);
    res.json({ actions: data });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.get('/ad/revenue', async (req, res) => {
  try {
    const data = await runPython('MBM.LeadEngine.ad_orchestrator', ['revenue']);
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── BUYERS ──────────────────────────────────────────────────────

router.get('/ad/buyers', async (req, res) => {
  try {
    // Direct JSON read from ad_storage (faster than spawning Python)
    const fs = await import('fs');
    const buyerPath = path.join(ROOT_DIR, 'ad_storage', 'buyer_buy_boxes.json');
    if (fs.existsSync(buyerPath)) {
      const buyers = JSON.parse(fs.readFileSync(buyerPath, 'utf8'));
      res.json({ buyers });
    } else {
      res.json({ buyers: [] });
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── DISPOSITION ─────────────────────────────────────────────────

router.get('/ad/disposition/summary', async (req, res) => {
  try {
    const data = await runPythonDirect(
      'MBM/LeadEngine/ad_disposition.py',
      ['--summary']
    );
    res.json(data);
  } catch (err) {
    // Fallback: empty summary
    res.json({ total: 0, by_outcome: {}, dnc_count: 0, follow_up_needed: 0 });
  }
});

router.get('/ad/disposition/recent', async (req, res) => {
  try {
    const limit = req.query.limit || 50;
    const data = await runPythonDirect(
      'MBM/LeadEngine/ad_disposition.py',
      ['--recent', String(limit)]
    );
    res.json(data);
  } catch (err) {
    res.json({ dispositions: [] });
  }
});

router.post('/ad/disposition', async (req, res) => {
  try {
    const { lead_id, outcome, notes, follow_up_channel, dnc_reason } = req.body;
    if (!lead_id || !outcome) {
      return res.status(400).json({ ok: false, errors: ['lead_id and outcome required'] });
    }

    // Write disposition via Python
    const args = [
      '--record',
      '--lead-id', lead_id,
      '--outcome', outcome,
    ];
    if (notes) args.push('--notes', notes);
    if (follow_up_channel) args.push('--follow-up-channel', follow_up_channel);
    if (dnc_reason) args.push('--dnc-reason', dnc_reason);

    const data = await runPythonDirect('MBM/LeadEngine/ad_disposition.py', args);
    res.json(data);
  } catch (err) {
    res.status(500).json({ ok: false, errors: [err.message] });
  }
});

// ─── FOLLOW-UPS ──────────────────────────────────────────────────

router.get('/ad/followups', async (req, res) => {
  try {
    const data = await runPythonDirect(
      'MBM/LeadEngine/ad_followup_executor.py',
      ['summary']
    );
    res.json(data);
  } catch (err) {
    res.json({ total_pending: 0, overdue: 0, due_now: 0, by_channel: {} });
  }
});

router.post('/ad/followups/execute', async (req, res) => {
  try {
    const limit = req.body.limit || 10;
    const data = await runPythonDirect(
      'MBM/LeadEngine/ad_followup_executor.py',
      ['execute', String(limit)]
    );
    res.json({ results: data });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── FEEDBACK LOOP ───────────────────────────────────────────────

router.get('/ad/feedback', async (req, res) => {
  try {
    const data = await runPythonDirect(
      'MBM/LeadEngine/ad_acquisition_loop.py',
      ['--metrics']
    );
    res.json(data);
  } catch (err) {
    res.json({ funnel: {}, source_quality: [], velocity: {} });
  }
});

router.get('/ad/feedback/sources', async (req, res) => {
  try {
    const data = await runPythonDirect(
      'MBM/LeadEngine/ad_acquisition_loop.py',
      ['--sources']
    );
    res.json({ sources: data });
  } catch (err) {
    res.json({ sources: [] });
  }
});

// ─── CONTENT ATTRIBUTION ─────────────────────────────────────────

router.get('/ad/attribution/content', async (req, res) => {
  try {
    const data = await runPythonDirect(
      'MBM/LeadEngine/ad_content_attribution.py',
      ['--content-performance']
    );
    res.json({ content: data });
  } catch (err) {
    res.json({ content: [] });
  }
});

router.get('/ad/attribution/campaigns', async (req, res) => {
  try {
    const data = await runPythonDirect(
      'MBM/LeadEngine/ad_content_attribution.py',
      ['--campaign-performance']
    );
    res.json({ campaigns: data });
  } catch (err) {
    res.json({ campaigns: [] });
  }
});

// ─── DATA PROVIDERS ──────────────────────────────────────────────

router.get('/ad/providers/health', async (req, res) => {
  try {
    const data = await runPythonDirect(
      'MBM/LeadEngine/ad_data_providers.py',
      ['--health']
    );
    res.json(data);
  } catch (err) {
    res.json({ providers: {} });
  }
});

export default router;
