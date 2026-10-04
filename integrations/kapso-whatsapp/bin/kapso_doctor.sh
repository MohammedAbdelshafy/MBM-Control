#!/usr/bin/env bash
# kapso_doctor.sh — environment + CLI health check for the Kapso WhatsApp channel.
#
# Checks, in order:
#   1. node and npm are on PATH
#   2. @kapso/cli is resolvable (global `kapso` binary, else npx fallback) and reports a version
#   3. the CLI's real --help exposes the advertised commands (login / setup / status)
#   4. login/session state via `kapso status --output json` (best-effort, read-only)
#
# Exit codes:
#   0 — node, npm and the Kapso CLI are present; report printed
#   2 — something required is missing (node, npm, or CLI not installable/resolvable)
#
# This script NEVER logs in, provisions a number, or changes remote state.
# WhatsApp number provisioning happens only via the founder's interactive `kapso setup`.

set -u

PASS=0
FAIL=0
KAPSO_BIN=""
KAPSO_VERSION="unknown"
KAPSO_SOURCE=""

ok()   { PASS=$((PASS+1)); printf '  [OK]   %s\n' "$1"; }
fail() { FAIL=$((FAIL+1)); printf '  [FAIL] %s\n' "$1"; }

section() { printf '\n== %s ==\n' "$1"; }

main() {
    printf 'Kapso WhatsApp — environment doctor\n'
    printf 'Date: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # --- 1. node / npm -------------------------------------------------------
    section "1. node / npm"
    if command -v node >/dev/null 2>&1; then
        ok "node found: $(command -v node) ($(node --version 2>/dev/null || echo 'version unknown'))"
    else
        fail "node NOT found on PATH — install Node.js (>=18 recommended) first"
    fi
    if command -v npm >/dev/null 2>&1; then
        ok "npm found: $(command -v npm) ($(npm --version 2>/dev/null || echo 'version unknown'))"
    else
        fail "npm NOT found on PATH — install npm alongside Node.js"
    fi
    if [ "$FAIL" -gt 0 ]; then
        printf '\nRESULT: missing prerequisites — install Node.js + npm, then re-run.\n'
        exit 2
    fi

    # --- 2. resolve the kapso CLI --------------------------------------------
    section "2. @kapso/cli resolution"
    if command -v kapso >/dev/null 2>&1; then
        KAPSO_BIN="kapso"
        KAPSO_SOURCE="global install ($(command -v kapso))"
    else
        # npx fallback, pinned to the verified version, non-interactive
        if timeout 90 npx -y @kapso/cli@0.19.0 --version >/dev/null 2>&1; then
            KAPSO_BIN="npx -y @kapso/cli@0.19.0"
            KAPSO_SOURCE="npx one-shot @kapso/cli@0.19.0 (not installed globally)"
        fi
    fi

    if [ -z "$KAPSO_BIN" ]; then
        fail "@kapso/cli could not be resolved — neither 'kapso' on PATH nor npx fetch worked"
        printf '       Fix: run  npm install -g @kapso/cli\n'
        printf '\nRESULT: Kapso CLI unavailable.\n'
        exit 2
    fi
    ok "CLI resolvable via: $KAPSO_SOURCE"

    # --- 3. version + real --help --------------------------------------------
    section "3. CLI version + advertised commands"
    KAPSO_VERSION="$($KAPSO_BIN --version 2>/dev/null | tr '\n' ' ' | sed 's/^ *//;s/ *$//')"
    if [ -n "$KAPSO_VERSION" ]; then
        ok "kapso --version => $KAPSO_VERSION"
    else
        fail "kapso --version returned nothing"
    fi

    HELP_TEXT="$($KAPSO_BIN --help 2>/dev/null || true)"
    if [ -z "$HELP_TEXT" ]; then
        fail "kapso --help produced no output"
    else
        ok "kapso --help returned output ($(printf '%s' "$HELP_TEXT" | wc -l | tr -d ' ') lines)"
    fi

    for cmd in login setup status; do
        if printf '%s' "$HELP_TEXT" | grep -qE "(^|[[:space:]])${cmd}([[:space:]]|$)"; then
            ok "--help advertises '$cmd' command"
        else
            fail "--help does NOT advertise '$cmd' — advertised 2-command flow may be broken"
        fi
    done

    # --- 4. login / session state --------------------------------------------
    section "4. login / project session state (read-only)"
    STATUS_OUT="$(timeout 60 $KAPSO_BIN status --output json 2>&1 || true)"
    if printf '%s' "$STATUS_OUT" | grep -qiE 'not logged|no login|unauthori|login required|no project|not linked'; then
        printf '  [INFO] kapso status reports: NOT logged in / no project linked.\n'
        printf '  [INFO] This is expected before first setup. Founder action required:\n'
        printf '         npm install -g @kapso/cli && kapso setup\n'
        printf '         (interactive — links a Kapso account and provisions/links a WhatsApp number)\n'
    elif [ -n "$STATUS_OUT" ]; then
        printf '  [INFO] kapso status output (first 20 lines):\n'
        printf '%s\n' "$STATUS_OUT" | head -20 | sed 's/^/         /'
    else
        printf '  [INFO] kapso status produced no usable output (possibly not logged in).\n'
    fi

    # --- summary ---------------------------------------------------------------
    printf '\n'
    printf 'RESULT: %d checks passed, %d failed\n' "$PASS" "$FAIL"
    if [ "$FAIL" -eq 0 ]; then
        printf 'STATUS: READY FOR FOUNDER SETUP — environment is good.\n'
        printf 'Next (founder, interactive): npm install -g @kapso/cli && kapso setup\n'
        exit 0
    else
        printf 'STATUS: BLOCKED — see failures above.\n'
        exit 2
    fi
}

main "$@"
