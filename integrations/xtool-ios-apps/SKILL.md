# Skill: xtool-ios-apps (iPhone apps without a Mac)

Build, sign, install, and launch iOS apps from a Linux/WSL terminal with
**xtool** — the VibeFounder power #12 pattern (xtool-org/xtool, MIT,
~12.8K stars, verified 2026-10-20). No Mac needed for day-to-day
development; no API key; the tool itself is free and open source.

## When to use

- A local business (clinic, gym, cafe — the same buyer classes as the
  Dr. Mia / AI Front Desk pitch) wants an iPhone app and you have no Mac.
- The swarm needs an iOS build lane on the Linux/WSL host next to the
  existing web-app pipeline.
- Anyone asks "can we ship an iPhone app without buying a Mac?"

## Python API

```python
import sys
sys.path.insert(0, "/home/hatch/workspace/night-shift/xtool-ios-apps")
import xtool_client as x

x.probe()                        # {"installed": True/False, "path": ..., "help_banner": [...]}
x.project_new("ClinicApp", dest_dir="/tmp")   # xtool new ClinicApp
x.list_devices()                   # raw device lines (not parsed — format not asserted)
x.project_dev("/tmp/ClinicApp")    # build + install + launch on the USB iPhone
x.install_ipa("/tmp/ClinicApp.ipa")
x.launch_app("com.example.clinicapp")   # passthrough; see `xtool launch --help`
print(x.setup_guide())             # one-time host recipe
```

`dry_run=True` on any call echoes the exact argv without executing.

## MCP server

```bash
python3 /home/hatch/workspace/night-shift/xtool-ios-apps/mcp_server.py
# stdio JSON-RPC. Tools: xtool_probe, xtool_devices, xtool_project_new,
# xtool_project_dev, xtool_app_install, xtool_app_launch, xtool_setup_guide
```

## Activation (one-time, on the build host)

```bash
# 1. Install xtool per https://xtool.sh/documentation/xtool/ (Linux/WSL/macOS)
# 2. Swift toolchain (xtool calls it)
# 3. iOS SDK: extract from Xcode.xip with your Apple ID, then `xtool sdk`
# 4. `xtool auth` (free Apple ID works for on-device dev)
# 5. Plug in a real iPhone over USB and trust the computer
xtool setup && cd /tmp && xtool new ClinicApp && cd ClinicApp && xtool dev
```

## Rules

- Never promise a client an App Store listing without the $99/year Apple
  Developer Program membership — xtool removes the Mac, not Apple.
- The SDK comes from Apple's Xcode distribution (Apple ID required); the
  non-Apple-hardware licensing question is a real gray area — say so, and
  keep final submissions on macOS per community practice.
- `xtool devices` output is returned raw on purpose; do not invent device
  field parsing. Flag shapes for install/launch/dev come from
  `xtool <subcommand> --help`, never from memory.
- Hermetic here: this machine has no Swift toolchain / SDK / iPhone, so
  end-to-end `xtool dev` is unverified — the wrappers and protocol are;
  see TEST_EVIDENCE.md.
