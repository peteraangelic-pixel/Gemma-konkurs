Re-fire of the V6.4 raw-call diagnosis with corrected call/observation pairing.

The first run (commit d686539) mis-paired calls with results, which showed an edit returning a grep
output. This run uses the fixed pairing plus four counters: edits with ok-looking results, edits
with error-looking results, comment-only commands, and reads beyond line 800.
