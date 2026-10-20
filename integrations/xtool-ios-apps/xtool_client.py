#!/usr/bin/env python3
"""xtool iOS-app-build orchestration client (VibeFounder power #12).

xtool (xtool-org/xtool, MIT, ~12.8K stars verified 2026-10-20) is a
cross-platform (Linux/WSL/macOS) Xcode replacement: it builds, signs,
installs, and launches iOS apps from SwiftPM packages without a Mac.
This module wraps the `xtool` CLI as checked subprocess calls so agents
can scaffold, build, and deploy iOS apps from a terminal.

Verified CLI surface (xtool README, checked 2026-10-20):
    xtool setup       Set up xtool for iOS development
    xtool auth        Manage Apple Developer Services authentication
    xtool sdk         Manage the Darwin Swift SDK
    xtool new         Create a new xtool SwiftPM project
    xtool dev         Build and run an xtool SwiftPM project
    xtool ds          Interact with Apple Developer Services
    xtool devices     List devices
    xtool install     Install an ipa file to your device
    xtool uninstall   Uninstall an installed app
    xtool launch      Launch an installed app

Honesty boundaries (nothing invented):
  - Flag shapes for install/launch/uninstall/dev are NOT asserted here:
    wrappers take an `extra_args` passthrough and always echo the exact
    argv they ran. `xtool <subcommand> --help` is the authority for flags.
  - `xtool devices` output format is not asserted: list_devices() returns
    the raw text plus a best-effort line split. No parsing of device fields
    is invented.
  - No live build is possible on this machine (no Swift toolchain, no iOS
    SDK, no iPhone attached). Hermetic tests use a mock `xtool` on PATH.
  - The iOS SDK itself still comes from Apple's Xcode distribution (needs an
    Apple ID); running Apple SDK binaries on non-Apple hardware is a debated
    licensing gray area — see README.md.

Stdlib only. A mock `xtool` binary can be injected via PATH for fully
hermetic tests (see make_mock_xtool).
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

__version__ = "1.0.0"

BINARY = "xtool"

# Subcommands taken verbatim from the xtool README --help listing.
KNOWN_SUBCOMMANDS = {
    "setup": "Set up xtool for iOS development",
    "auth": "Manage Apple Developer Services authentication",
    "sdk": "Manage the Darwin Swift SDK",
    "new": "Create a new xtool SwiftPM project",
    "dev": "Build and run an xtool SwiftPM project",
    "ds": "Interact with Apple Developer Services",
    "devices": "List devices",
    "install": "Install an ipa file to your device",
    "uninstall": "Uninstall an installed app",
    "launch": "Launch an installed app",
}

OUTPUT_TRUNCATE_AT = 100_000  # chars; mark truncation instead of logging megabytes


def _truncate(text: str) -> str:
    if len(text) > OUTPUT_TRUNCATE_AT:
        return text[:OUTPUT_TRUNCATE_AT] + f"\n...[truncated {len(text) - OUTPUT_TRUNCATE_AT} chars]"
    return text


def find_xtool() -> str | None:
    """Absolute path of the xtool binary on PATH, or None."""
    return shutil.which(BINARY)


def probe() -> dict:
    """Detect xtool and return its install state + help banner.

    Never invents a version: reports what `xtool --help` prints.
    """
    path = find_xtool()
    if not path:
        return {
            "installed": False,
            "path": None,
            "hint": "Install from https://xtool.sh/documentation/xtool/ "
                    "(Linux/WSL/macOS). Then run `xtool setup`.",
        }
    try:
        proc = subprocess.run(
            [path, "--help"], capture_output=True, text=True, timeout=30
        )
        banner = (proc.stdout or "").splitlines()[:8]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"installed": True, "path": path, "help_ok": False,
                "error": f"{type(exc).__name__}: {exc}"}
    return {
        "installed": True,
        "path": path,
        "help_ok": proc.returncode == 0,
        "help_banner": banner,
        "known_subcommands": sorted(KNOWN_SUBCOMMANDS),
    }


def run_xtool(
    subcommand: str,
    args: list[str] | None = None,
    *,
    cwd: str | Path | None = None,
    timeout: int = 600,
    dry_run: bool = False,
    env: dict | None = None,
) -> dict:
    """Run `xtool <subcommand> <args...>` and return a normalized result dict.

    dry_run=True echoes the exact argv without executing (pre-flight check).
    Unknown subcommands are refused — only the README-verified surface runs.
    """
    if subcommand not in KNOWN_SUBCOMMANDS:
        return {"ok": False, "argv": None,
                "error": f"refusing unknown subcommand {subcommand!r}; "
                         f"known: {sorted(KNOWN_SUBCOMMANDS)}"}
    path = find_xtool()
    argv = [path or BINARY, subcommand, *(args or [])]
    if dry_run or not path:
        return {"ok": False, "dry_run": dry_run, "argv": argv,
                "installed": bool(path),
                "error": None if dry_run else "xtool not found on PATH"}
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout,
            cwd=str(cwd) if cwd is not None else None,
            env=env if env is not None else os.environ,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "argv": argv,
                "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": proc.returncode == 0,
        "argv": argv,
        "returncode": proc.returncode,
        "stdout": _truncate(proc.stdout or ""),
        "stderr": _truncate(proc.stderr or ""),
    }


_PROJECT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def project_new(name: str, dest_dir: str | Path | None = None,
                dry_run: bool = False) -> dict:
    """Scaffold a new xtool SwiftPM project: `xtool new <name>` run in dest_dir.

    Refuses unsafe project names (shell-word safety, no path traversal).
    """
    if not _PROJECT_NAME_RE.match(name):
        return {"ok": False, "argv": None,
                "error": f"unsafe project name {name!r}; use [A-Za-z0-9._-], "
                         "start with alnum, max 64 chars"}
    return run_xtool("new", [name], cwd=dest_dir, dry_run=dry_run)


def project_dev(project_dir: str | Path, extra_args: list[str] | None = None,
                timeout: int = 1800, dry_run: bool = False) -> dict:
    """Build + install + run the project in project_dir: `xtool dev`.

    Needs a USB-connected iPhone (trusted) and a configured SDK/auth.
    Long timeout default: first builds fetch and compile a lot.
    """
    return run_xtool("dev", list(extra_args or []), cwd=project_dir,
                     timeout=timeout, dry_run=dry_run)


def list_devices(extra_args: list[str] | None = None,
                 dry_run: bool = False) -> dict:
    """`xtool devices` — returns raw output; device fields are NOT parsed."""
    result = run_xtool("devices", list(extra_args or []), dry_run=dry_run)
    if result.get("ok"):
        lines = [ln for ln in result["stdout"].splitlines() if ln.strip()]
        result["device_lines"] = lines
        result["device_line_count"] = len(lines)
    return result


def install_ipa(ipa_path: str | Path, extra_args: list[str] | None = None,
                dry_run: bool = False) -> dict:
    """`xtool install <ipa>` — install a built .ipa on the connected device."""
    ipa = Path(ipa_path)
    if not dry_run and not ipa.is_file():
        return {"ok": False, "argv": None,
                "error": f"ipa not found: {ipa}"}
    return run_xtool("install", [str(ipa), *(extra_args or [])],
                     dry_run=dry_run)


def launch_app(*app_args: str, dry_run: bool = False) -> dict:
    """`xtool launch ...` — passthrough; flag shapes come from `xtool launch --help`."""
    return run_xtool("launch", list(app_args), dry_run=dry_run)


def uninstall_app(*app_args: str, dry_run: bool = False) -> dict:
    """`xtool uninstall ...` — passthrough; flag shapes come from `xtool uninstall --help`."""
    return run_xtool("uninstall", list(app_args), dry_run=dry_run)


def ds(*ds_args: str, dry_run: bool = False) -> dict:
    """`xtool ds ...` — Developer Services passthrough (devices, certs, profiles)."""
    return run_xtool("ds", list(ds_args), dry_run=dry_run)


SETUP_GUIDE = """xtool setup guide (from xtool.sh docs + README, 2026-10-20)

PREREQUISITES (one-time, per host):
1. Host: Linux, Windows with WSL, or macOS.
2. Swift toolchain installed (xtool calls it; docs list Swift 6.4-era).
3. iOS SDK: extract from an Xcode.xip downloaded with your Apple ID —
   this step cannot be automated away (the SDK exists only inside Apple's
   Xcode distribution). Then `xtool sdk` manages it.
4. Apple Developer auth: `xtool auth` (free Apple ID works for on-device
   dev; App Store submission still needs the $99/year Developer Program).
5. A real iPhone + USB cable; trust the computer on the phone.

FIRST APP:
    xtool setup            # one-time host setup
    xtool sdk ...          # point at / install the SDK
    xtool new MyApp        # scaffold SwiftPM project
    cd MyApp
    xtool dev              # build, sign, install, launch on the phone

NOTES:
- App Store publishing still costs $99/year and needs Apple Developer
  Program membership.
- Free Apple ID login uses private APIs per xtool's docs — choose the
  login mode deliberately.
- Licensing caution: extracting Apple SDK binaries and running them on
  non-Apple hardware is a debated gray area in Apple's terms; community
  practice is dev/test on Linux/WSL, final submission from macOS.
"""


def setup_guide() -> str:
    """Return the one-time setup recipe as text (no host changes made)."""
    return SETUP_GUIDE


MOCK_SCRIPT = r"""#!/bin/sh
# Mock xtool for hermetic tests. Emulates exit codes + canned stdout.
sub="$1"; shift || true
case "$sub" in
  --help|-h)
    echo "OVERVIEW: Cross-platform Xcode replacement"
    echo "USAGE: xtool <subcommand>"
    exit 0;;
  new)
    echo "Creating package: $1"
    echo "Creating Package.swift"
    echo "Creating xtool.yml"
    echo "Finished generating project $1."
    exit 0;;
  dev)
    echo "Building..."
    echo "Installing to device..."
    echo "Launching..."
    exit 0;;
  devices)
    echo "mock-iphone-1 (iPhone, iOS 26.1, paired)"
    echo "mock-iphone-2 (iPhone, iOS 26.0, paired)"
    exit 0;;
  install)
    echo "Installing $1 ..."
    echo "Installed."
    exit 0;;
  launch)
    echo "Launching $@ ..."
    exit 0;;
  uninstall)
    echo "Uninstalled $@"
    exit 0;;
  auth)
    echo "mock: auth needs interactive login" >&2
    exit 3;;
  *)
    echo "mock xtool: unknown subcommand '$sub'" >&2
    exit 2;;
esac
"""


def make_mock_xtool(directory: str | Path, name: str = BINARY) -> str:
    """Write an executable mock `xtool` into directory; return its path."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(MOCK_SCRIPT, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


def self_check() -> dict:
    """Hermetic self-check: mock xtool on a temp PATH, exercise wrappers."""
    import tempfile

    tmp = tempfile.mkdtemp(prefix="xtool_client_check_")
    make_mock_xtool(tmp)
    env = dict(os.environ)
    env["PATH"] = tmp + os.pathsep + env.get("PATH", "")
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = env["PATH"]
    try:
        steps = {}
        steps["probe"] = probe()
        assert steps["probe"]["installed"] is True
        steps["new"] = project_new("SmokeApp")
        assert steps["new"]["ok"] is True, steps["new"]
        assert "Creating package: SmokeApp" in steps["new"]["stdout"]
        steps["dev"] = project_dev("/tmp")
        assert steps["dev"]["ok"] is True, steps["dev"]
        steps["devices"] = list_devices()
        assert steps["devices"]["ok"] is True
        assert steps["devices"]["device_line_count"] == 2
        steps["install"] = install_ipa("/tmp/SmokeApp.ipa", dry_run=True)
        assert steps["install"]["argv"][2] == "/tmp/SmokeApp.ipa"
        steps["launch"] = launch_app("com.example.smoke")
        assert steps["launch"]["ok"] is True
        steps["bad_subcommand"] = run_xtool("nope")
        assert steps["bad_subcommand"]["ok"] is False
        steps["bad_name"] = project_new("../../evil")
        assert steps["bad_name"]["ok"] is False
        steps["auth_fails"] = run_xtool("auth")
        assert steps["auth_fails"]["ok"] is False
        assert steps["auth_fails"]["returncode"] == 3
        steps["dry_run"] = project_new("DryApp", dry_run=True)
        assert steps["dry_run"]["dry_run"] is True
        return {"self_check": "PASS", "steps": sorted(steps)}
    finally:
        os.environ["PATH"] = old_path


if __name__ == "__main__":
    import json

    print(json.dumps(self_check(), indent=2))
