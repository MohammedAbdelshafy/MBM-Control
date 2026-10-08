# TEST EVIDENCE — swarm-orchestrator (VibeFounder power #6)

**Date:** 2026-10-06 | **Run:** `vibefounder-night-shift` | **Command:** `python3 test_smoke.py`
**Result: 8/8 PASS** — hermetic (mock backends on a temp PATH; no network, no real CLIs, no keys).

```
PASS self_check — 2 mock results, roles ['coder']
PASS detect_mocks — 3 mock backends detected on PATH
PASS dispatch_parallel — 3 results in 0.01s, all exit 0
PASS dispatch_roles — roles in order on ['smoke-a', 'smoke-b', 'smoke-c']
PASS dispatch_subset_and_dryrun — subset + dry_run argv echo OK
PASS role_wrappers — 3 wrappers format cleanly
PASS events_roundtrip — 5 recent events readable
PASS mcp_protocol — 5 tools over stdio; error path OK
```

What each test proves:

| # | Test | Proves |
|---|---|---|
| 1 | self_check | `orchestrator.self_check()` passes on a fresh temp PATH with 2 mocks |
| 2 | detect_mocks | `shutil.which` scan finds all 3 injected mock CLIs + version probing shape |
| 3 | dispatch_parallel | 3 backends run concurrently (0.01s), all exit 0, outputs captured |
| 4 | dispatch_subset_and_dryrun | subset selection works; dry_run echoes exact argv, executes nothing |
| 5 | roles | researcher→coder→reviewer order preserved; assignments map to real mocks |
| 6 | role_wrappers | all 3 role prompt wrappers format without KeyError |
| 7 | events_roundtrip | JSONL event log append + read-back works |
| 8 | mcp_protocol | stdio JSON-RPC: initialize → tools/list (5 tools) → tools/call for all tools → error path returns isError |

**Not tested here (documented, not claimed):** real CLI backends (`claude`,
`codex`, `gemini`, `qwen`, `opencode`) — none are installed on this VM, so
live dispatch is untested. `WIRING.md` states this plainly. Activation = a
logged-in CLI on the host machine.

**Verification appendix:**
- Munder Difflin canonical repo: `HarnessMD/munder-difflin`, 8,483 stars,
  MIT, updated 2026-10-05 (GitHub API, 2026-10-06).
