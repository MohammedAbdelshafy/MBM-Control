# TEST_EVIDENCE.md — xtool-ios-apps (power #12)

**Run:** 2026-10-20 ~02:50 EEST (night-shift run)
**Command:** `python3 test_smoke.py` in `~/workspace/night-shift/xtool-ios-apps/`
**Result: 9/9 PASS.** No network, no real xtool, no Swift toolchain, no iPhone.

```
PASS client_self_check — steps: auth_fails, bad_name, bad_subcommand, dev, devices, dry_run, install, launch, new, probe
PASS probe_banner — banner ok, 10 known subcommands
PASS devices_raw — 2 mock device lines returned raw
PASS project_new_argv — argv=['/tmp/xtool_smoke_zq0y43z0/xtool', 'new', 'MyApp']
PASS unsafe_name_refused — 5 unsafe names refused
PASS unknown_subcommand_refused — refused as designed
PASS missing_ipa_refused — missing ipa refused before any subprocess
PASS setup_guide_content — guide covers setup, SDK, fee, WSL
PASS mcp_roundtrip — init/list/7 tool calls + unknown-tool error, no notification hang
```

**What each step proves:**
- `client_self_check`: the client's own mock-PATH exercise — probe, `new`,
  `dev`, `devices`, install argv echo, `launch`, unknown-subcommand refuse,
  unsafe-name refuse, nonzero-exit propagation (mock `auth` exits 3),
  dry-run echo. All pass in-process.
- `probe_banner`: `xtool --help` on the mock emits the real banner text
  ("Cross-platform Xcode replacement") and all 10 README-verified
  subcommands are registered.
- `devices_raw` / `project_new_argv`: raw passthrough behavior and exact
  argv shapes confirmed against the mock.
- `unsafe_name_refused`: `../../evil`, `a b`, empty, 65-char, and
  dash-leading names are all refused before any subprocess spawns.
- `unknown_subcommand_refused`: `run_xtool("pwn")` refuses — the wrapper
  cannot be used to run arbitrary xtool surface.
- `missing_ipa_refused`: nonexistent `.ipa` refused before any subprocess.
- `setup_guide_content`: the recipe contains `xtool setup`, the `Xcode.xip`
  SDK step, the `$99` fee note, and the WSL path.
- `mcp_roundtrip`: spawned `mcp_server.py` over stdio — initialize,
  `notifications/initialized` sent with no id (server correctly stays
  silent — no hang), `tools/list` returns 7 tools, all 7 tools called
  successfully, unknown tool returns `isError`.

**Not verified here (stated plainly):** end-to-end `xtool dev` against a
real Swift toolchain + iOS SDK + iPhone. This VM has none of the three;
the integration is hermetically tested. Live verification = run
`xtool_setup_guide` on the build host and `xtool dev` a scaffolded project
there.

**Verification of the underlying tool (2026-10-20):**
- GitHub `xtool-org/xtool`: public, MIT license, 12,828 stars, 421
  commits, active (current commit `8c46156e27fcd5874acfa3725b29defdee809184`
  at check time). README `--help` surface matches the wrapper's
  KNOWN_SUBCOMMANDS exactly.
- Caveats cross-checked: xtool.sh docs (SDK from Xcode.xip, private-API
  free-login note) + frontiernow.dev teardown 2026-10-10 (licensing gray
  area on non-Apple hardware; $99 fee for store submission).
