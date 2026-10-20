# WIRING.md — where xtool-ios-apps plugs into the founder's stack

Power #12 (xtool: build iPhone apps without a Mac) maps to a **new
service lane**, not a rebrand of an existing product: it removes the one
hardware excuse between the founder and iPhone-app work for local
businesses. Buyer classes are the same ones the Dr. Mia / AI Front Desk
pitches already target (clinics, gyms, cafes) — the app lane cross-sells
naturally with the quality-manager / front-desk offers.

## Lane 1 — "iPhone app for your business" service (new opportunity)

Offer shape (concept — needs a founder pricing call, not built here):
a booking/rewards/info iPhone app for a local business, built with
Claude Code + xtool on the founder's Linux/WSL host, no Mac purchase.

Delivery path with this integration:
1. `xtool_setup_guide` (MCP) → one-time host setup checklist.
2. `xtool_probe` → confirm the toolchain on the build host.
3. `xtool_project_new {"name": "ClientApp"}` → scaffold.
4. Claude Code writes the SwiftUI app inside the scaffold (existing swarm
   lane, power #6).
5. `xtool_project_dev {"project_dir": ...}` → build + install on a test
   iPhone; iterate.
6. `xtool_app_install` for client-side test builds; TestFlight/App Store
   submission still needs the client's (or founder's) $99/year Developer
   Program membership — price that into the quote.

Guardrails: never quote an App Store listing without the membership;
state the SDK-licensing gray area to the client in writing; first paid
build should be dev/test distribution, not store submission.

## Lane 2 — swarm backend (MBM-Control)

`xtool-ios-apps` sits beside `swarm-orchestrator` (power #6): the swarm's
coder agents can now target iOS via the same headless pattern —
`xtool_project_dev` with `dry_run=true` as the pre-flight check, real runs
only on the configured build host. No swarm code changes needed; the MCP
server is the interface.

## Lane 3 — pitch-deck widget (bolt-slides, power #8)

The interactive pitch decks already carry a "messy list → clean list" demo
widget. An iPhone-app lane adds a fourth demo widget candidate:
"describe your business → see the app scaffold" (scaffold-only,
`xtool_project_new` dry-run output rendered in the deck). Deferred to a
future deck iteration — noted, not built.

## What this does NOT do

- It does not replace the DataClean AI / Wholesaler / Dr. Mia products.
- It does not automate App Store review, signing identities, or the
  Apple Developer Program.
- It does not run on this VM (no Swift toolchain, SDK, or iPhone) —
  it is a build-host integration, hermetically tested here.
