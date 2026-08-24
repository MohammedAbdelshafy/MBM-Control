# NEXT_SPRINT (M-023 follow-up)

Ranked by ROI and leverage. Each item links to its GitHub issue.

## P0 — unblock ACTUAL economics (highest ROI)
- **#22 Verify reward rates from official program sources.** Set
  `reward_attribution.RewardRateRegistry` entries `verified=True` with source +
  as_of for YouTube PPP, TikTok Creator Rewards, Instagram Bonus, X Amplify.
  Unlocks ACTUAL revenue/ROI reporting (currently ESTIMATED-only) and improves
  learning priors immediately. Lowest engineering, highest signal.

## P1 — real signal quality
- **#19 faster-whisper transcription integration.** Wire ASR as the speech
  factory so `candidate_pool` scores on real hook/speech/visual signals instead
  of synthetic defaults. Lifts selection quality across all 5 brands.
- **#18 active-speaker/face detection.** Integrate a local detector to emit
  `ReframeRegion` so `video_editing.choose_reframe_filter` keeps subjects in
  frame (9:16). Today it center-crops.

## P2 — platform coverage
- **#20 LinkedIn + X publisher implementations.** Implement `publisher.py`
  adapters + provision API apps. Mark BLOCKED today; must never report
  Published without a real id.
- **#21 Instagram + TikTok automated publishing.** Provision Graph API /
  TikTok Content Posting API; add real `verify_publish`. Keep MANUAL until then.

## P3 — throughput & dashboards
- Benchmark real render throughput (FFmpeg/GPU) and publish against platform
  rate limits; feed `distribution_optimizer` live performance for auto-scaling.
- Expose `observability.snapshot()` to the existing dashboard / event bus.
- Restore YouTube Analytics API scopes so `verify_analytics` returns real
  watch-time/retention (feeds `learning_feedback.record_analytics`).

## Definition of done for the sprint
- ACTUAL revenue reported for ≥1 brand (not estimated).
- Candidate pool fed by real ASR.
- LinkedIn and/or X publish end-to-end in a sandbox.
- Render throughput measured and within `distribution_optimizer` caps.
