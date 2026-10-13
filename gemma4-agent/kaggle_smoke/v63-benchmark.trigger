user-authorized full V6.3 screening (benchmark only, no official submission); account=petersharps
candidate: V6.3 (prompt-quality build)
archive: gemma4-agent/submission-v6.zip
archive_sha256: 650e1dba10c5b269c616a670255c3a585a57d750ce0f8428581ae65ea528f5c4
task_count: 30
task_id: fastapi_15588
seed: 20261009
comparison_baseline: V3 11/30, V4 11/30, V5 10/30, V6.1 6/30, V6.2 9/30 on this exact sample
artifact_identity: the V6.3 mini-screen ran archive abf22bac...; this run uses 650e1dba..., which
  differs from abf22bac ONLY in prompt prose (verified by unified diff: 11 changed lines - the
  stale "45 tool calls" text corrected to 30, a duplicated verification sentence removed, and two
  bullets that a Python line continuation had glued together now on their own lines). No rule,
  threshold, script byte or config differs. The arm the mini-screen validated is therefore the
  same arm this run measures.
pre_registered_gates: gemma4-agent/GATES_V6_3.md (G1 zero scratch files, G2 zero premature submits without edits, G3 zero docs-only diffs; G4 empty trees <= 4 reported separately)
official_submission: false
