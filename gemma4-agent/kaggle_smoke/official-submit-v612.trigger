Arm the V6.12 send for the night of 15/16 October 2026.

Pushed at 22:45 UTC on 15 Oct, i.e. 80 minutes before the competition's daily submission slot
refreshes, so the job waits and uploads at 00:05 UTC on the 16th (02:05 Warsaw). Sending on the
push instead would have consumed the 15th's slot and, under the rolling 24-hour rule, kept the
whole of the 16th blocked - the window in which the Saturday arm results have to be judged.

What goes up: submission-v6.12.zip, sha256 5381ae17398f88ba434313439d9b784103dbab514bd7a0a3798a142f3c84c515,
message "V6.12". That is the V6.10 composition (V6.7 contract + evolved locator + inline delivery)
plus V6.11's four conversion rules, inside V5's proven budget envelope: 150 s / 45 calls / 80 turns
/ 5.25 min. The 8-minute clock of V6.11 is deliberately excluded - 120 x (8 + 0.5) min projects to
17 h against a 12-hour limit whose breach errors the entire submission, and the shorter mean that
would make it safe has not been measured yet (that is the Saturday S1 gate).

The guard chain still runs inside the job: the archive must match the pinned sha256, the message
must not exist in the competition history, and no submission may exist from today or the last 24 h.
See gemma4-agent/GATES_V6_12.md for the frozen gates and the pre-registered reading of the score.
