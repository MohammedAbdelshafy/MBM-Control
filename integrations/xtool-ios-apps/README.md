# xtool-ios-apps — build iPhone apps without a Mac (VibeFounder power #12)

Stdlib-only Python client + MCP stdio server wrapping the **xtool** CLI
([xtool-org/xtool](https://github.com/xtool-org/xtool), MIT, ~12.8K stars
verified 2026-10-20): a cross-platform (Linux/WSL/macOS) Xcode replacement
that builds, signs, installs, and launches iOS apps from SwiftPM packages —
no Mac required for day-to-day development.

## What it does

- `xtool_client.py` — checked subprocess wrappers around the README-verified
  xtool subcommands: `setup`, `auth`, `sdk`, `new`, `dev`, `ds`, `devices`,
  `install`, `uninstall`, `launch`. Only that surface can run; anything else
  is refused. Unsafe project names are rejected; exact argv is always echoed.
  `dry_run=True` is the pre-flight mode.
- `mcp_server.py` — JSON-RPC 2.0 stdio MCP server, 7 tools:
  `xtool_probe`, `xtool_devices`, `xtool_project_new`, `xtool_project_dev`,
  `xtool_app_install`, `xtool_app_launch`, `xtool_setup_guide`.
- `test_smoke.py` — 9 hermetic tests (mock `xtool` on PATH, in-process MCP
  round trip). No network, no Swift toolchain, no iPhone.

## Quick start

```bash
cd ~/workspace/night-shift/xtool-ios-apps
python3 test_smoke.py          # 9/9 pass, zero external deps

python3 mcp_server.py          # stdio JSON-RPC; tools/list to inspect
```

Wire into Claude Code / Cursor:

```json
{"mcpServers": {"xtool-ios-apps": {
  "command": "python3",
  "args": ["/home/hatch/workspace/night-shift/xtool-ios-apps/mcp_server.py"]}}}
```

Python use:

```python
import sys
sys.path.insert(0, "/home/hatch/workspace/night-shift/xtool-ios-apps")
import xtool_client as x

x.probe()                                   # is xtool installed?
x.project_new("ClinicApp", dest_dir="/tmp") # xtool new ClinicApp
x.list_devices()                            # raw device lines
x.project_dev("/tmp/ClinicApp", dry_run=True)  # pre-flight argv echo
print(x.setup_guide())                      # one-time setup recipe
```

## Honest limits (read before promising anything)

1. **No live build was run here.** This VM has no Swift toolchain, no iOS
   SDK, and no iPhone — all tests run against a mock `xtool`. The wrappers
   are verified; the end-to-end `xtool dev` on real hardware is not.
2. **The iOS SDK is Apple's.** It exists only inside Apple's Xcode
   distribution; you extract it from an `Xcode.xip` downloaded with an
   Apple ID. That step cannot be automated away, and running Apple SDK
   binaries on non-Apple hardware is a debated licensing gray area.
   Community practice: dev/test on Linux/WSL, final submission from macOS.
3. **App Store submission still costs $99/year** (Apple Developer Program)
   and needs membership — xtool removes the Mac, not Apple.
4. **Free Apple ID login uses private APIs** per xtool's own docs — choose
   the login mode deliberately.
5. `xtool devices` output format is deliberately NOT parsed — the tool
   returns raw lines. Flag shapes for `install`/`launch`/`dev` are passed
   through, not asserted; `xtool <sub> --help` is the authority.

## Provenance

- Power extracted from @thevibefounder reel 2026-10-18
  ("Build iPhone Apps Without a Computer" — xtool + Claude Code on Windows).
- Tool verified via GitHub: `xtool-org/xtool`, public, MIT, 12,828 stars,
  421 commits, updated 2026-10 (current commit `8c46156` at check time).
- Legal/technical caveats cross-checked against xtool.sh docs and the
  2026-10 frontiernow.dev teardown (SDK-extraction requirement,
  pymobiledevice3/rcodesign chain, licensing debate).
