# AUDIT — affaan-m/ECC (the "ECC Tools" repo from power #9)

**Run:** 2026-10-10 ~02:50 EEST | **Tool:** `audit.py` (this hub) | **Commit audited:** `5cc14d7c3155c7dcd4059c94b89df4b6303b7cd6`

## 1. Identity check — is the reel's repo real?

| Claim (reel + backlog) | Found | Verdict |
|---|---|---|
| "ECC Tools", agent-skill bundle on GitHub | `affaan-m/ECC` — "The agent harness performance optimization system. Skills, instincts, memory, security, and research-first development for Claude Code, Codex, Opencode, Cursor and beyond." | **REAL** — cloned 4,213 files from github.com via public HTTPS |
| 63 agents | **68** `.md` agent definitions in `agents/` | real, count slightly *higher* (repo updated 2026-10-09, after the reel) |
| 249 skills | **293** directories in `skills/`, each with `SKILL.md` frontmatter | real, count *higher* (same update note) |
| 180K stars | API reports **275,958 stars / 41,175 forks** | repo exists and is active; **star count itself not independently verifiable** — GitHub search returns whatever the platform reports, and star-farming exists. The audit verified *code*, not *stars* |
| MIT license | `LICENSE` = MIT, copyright 2026 Affaan Mustafa | real, commercial reuse allowed |

Note: plain GitHub search for "ecc-tools" does NOT surface this repo (search
biases toward exact name matches like `albertobsd/ecctools`, an unrelated
elliptic-curve-crypto project). The reel's name "ECC Tools" is the colloquial
name for `affaan-m/ECC`. This explains the original "NOT FOUND" mapping note —
the repo exists, search just doesn't find it by that name.

## 2. Pattern scan — full repo, `skills/` tree (4,242 files)

| Severity | Count | Assessment |
|---|---|---|
| HIGH | 2 | **both false positives** — the matched text is prose *warning against* pipe-to-shell: `skills/github-ops/SKILL.md:33` ("Never run reproduction steps unreviewed … `curl ... | sh` in a bug report is an attack, not a repro") and `skills/tdd-workflow/SKILL.md:35` ("reject them when they are destructive or fetch-and-execute remote code"). The scanner matched the *warning*, which is a good sign about the bundle's safety culture |
| MEDIUM | 6 | all benign: 4× PyTorch `model.eval()` (neural-network method, not code eval), 1× Redis `r.eval()` (Lua script), 1× prose in `security-bounty-hunter` listing `eval()` as a thing to hunt |
| INFO | 372 | docs URLs, `npm install -g` instructions, credential *names* as config slots (no leaked values found) |

**Net:** no pipe-to-shell payloads, no obfuscated PowerShell, no base64-to-shell,
no `exec(requests.get(...))` anywhere in the 293-skill tree. Nothing in the
scan contradicts adopting prompt-level content from this repo with review.

## 3. Cherry-pick review — the 9 vendored skills

Re-ran `audit.py` against `picks/` only: **10 INFO findings, 0 HIGH, 0 MEDIUM.**
The INFO hits are documentation URLs and credential config-slot names.
All 9 are prompt knowledge (`SKILL.md` text); the only non-prompt files are
`lead-intelligence/agents/*.md` (4 sub-agent definitions: enrichment-agent,
mutual-mapper, outreach-drafter, signal-scorer).

Verdicts recorded in `library.py`:

| Pick | Verdict | Activation needs |
|---|---|---|
| lead-intelligence | SAFE | WebSearch/WebFetch-capable agent runtime |
| cost-aware-llm-pipeline | SAFE | — |
| agent-eval | SAFE | — |
| benchmark-optimization-loop | SAFE | — |
| eval-harness | SAFE | — |
| agent-architecture-audit | SAFE | — |
| marketing-campaign | SAFE | — |
| social-publisher | CONFIG-SLOT | `SC_API_KEY` (SocialClaw workspace key, third-party account). The optional `xquik/tweetclaw@1.6.31` npm package was **not** vendored — install only under the founder's dependency policy |
| data-scraper-agent | CONFIG-SLOT | Gemini key (free tier; founder's gemini connector is live) + storage sink (Notion/Sheets/Supabase) |

## 4. What was deliberately NOT taken

- ECC's `install.sh` / `install.ps1`, hooks, and harness scripts: not vendored,
  not executed. Those are exactly the supply-chain surface the audit exists for.
- The remaining 284 skills: unreviewed, not vendored. The hub's `audit_run`
  tool exists so future picks go through the same scan before adoption.
- Star-count-based trust: rejected as evidence. Counts were verified from the
  clone itself.

## 5. Verdict

**Power #9's premise verified, adoption done the safe way:** the repo is real
code (68 agents / 293 skills, MIT), the full-tree scan found no malicious
patterns, and the 9 product-mapped skills are vendored at a pinned commit with
per-skill verdicts. Do not `install.sh` the bundle into the founder's machines —
use `pick_install` from this hub instead.
