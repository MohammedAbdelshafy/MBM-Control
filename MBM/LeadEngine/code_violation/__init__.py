"""code_violation -- daily municipal code-violation lead engine.

Safe, additive pipeline inside the existing MBM lead/dialer ecosystem:

  collector   -> municipal open-data sources (Socrata + ArcGIS REST)
  enrichment  -> DCAD / county-routed owner verification + skip-trace phone
  scoring     -> mission signal scoring + TIER 1/2/3
  pipeline    -> dedup (case ledger + live dialer) -> dialer sync via
                 patch_dialer_db -> GTM daily artifacts + founder report

Run:  `npm run leads:violations` (dry-run) / `npm run leads:violations:apply`.
"""
