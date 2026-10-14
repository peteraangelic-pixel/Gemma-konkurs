Official V5 submission - fired 2026-10-14 ~03:50 UTC, on the user's explicit go ("Tak - wysylaj V5 teraz").

Why V5 and not anything else, one more time, so the record stands on its own:
- V5 is the only unsubmitted candidate that passes our own frozen send criteria S1-S3
  (bench 10/30 >= 10; 6 empty trees <= 8; G1 = G3 = 0 and G2 = 1 <= 1).
- V4 already carries the official 0.03, so resubmitting it adds nothing.
- V6.3 is forbidden (G2 = 3), V6.4 fails S2 and S3 (11 empty trees, G2 = 3), V6.5/V6.6 were never
  measured (the 2026-10-14 GPU-quota incident) and have no submitter by design.
- V5 flips the three levers a peer ablation measured as the biggest ones (thinking summaries ON:
  51/129 vs 35; temperature 0.4 vs 0.2; 45 vs 35 tool calls) and removes the analyzer/skills/
  public-repo hints that could not transfer to the hidden split.

Mechanics: the workflow stages gemma4-agent/submission-v5.zip as the canonical submission.zip, and
the submitter refuses to upload unless the archive hash equals 282b1446... (verified: the blob on
this branch and the file on disk both hash to exactly that), unless no submission with the message
"V5" exists yet, and unless the daily slot is free (the rules allow one submission per day; the last
one was V4 on 2026-10-10 14:51:48 UTC). The receipt lands in
gemma4-agent/kaggle_results/v5-official-submission.json and the workflow deletes this file in its
receipt commit.

Expectation before seeing any result: status PENDING, then a public score in roughly 22-46 hours
(peer-reported scoring queue). This is a bet on the ablation-driven settings transferring to the
hidden split, not on the public sample, where V5 (10/30) and V4 (11/30) are statistically
indistinguishable.
