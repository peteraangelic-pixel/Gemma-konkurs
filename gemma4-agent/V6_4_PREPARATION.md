# V6.4 candidate preparation (offline)

**Status:** prepared locally; not benchmarked and not submitted. No Kaggle action is part of this candidate.

## Candidate files

- Package directory: `gemma4-agent/submission-v6.4/`
- Reproducible packer: `gemma4-agent/build_submission_v64.py`
- Intended archive: `gemma4-agent/submission-v6.4.zip`
- Baseline source: V6.3 files at reference commit `3ee7dd28053df6899e5f9f708999263f5e059dd0` on `arena/c4eeb067-gemma-konkurs`.

## Isolated intervention

V6.4 targets empty-tree sessions with two separately reversible changes:

1. `prompts/system.md` requires a first intended source/configuration edit by tool call 4 (from call 8 in V6.3). It narrows the initial inspection window and explicitly says not to delay that edit for tests/search. It also fixes the conflicting scratch-file instructions around the one `/tmp/locate.py` heredoc.
2. `agent.yaml` no longer registers `submit_patch`. The prompt had called it optional, while the tool description said it always submits and its invocation ends the session. Removing the tool is intended to prevent an early empty termination.

Both levers are enabled in the packaged candidate, but remain in separate files so they can be ablated later. A result from this combined package alone must not be attributed to either lever individually.

**Important assumption:** the candidate relies on the harness collecting the working-tree diff on session end, as documented in the prompt. This fallback has not been end-to-end verified for V6.4. Removing `submit_patch` is therefore a hypothesis, not a validated fix.

## Preserved settings

The model, locator, remaining tool registrations, thinking/sampling settings, and evaluation limits are unchanged from the copied V6.3 baseline: model `gemma-4-31b-it-qat-w4a16-ct`; thinking budget 4096 with thoughts included; 30 tool calls; 5.25 minutes; 150-second timeout; 60 max turns. The locator implementation is copied unchanged.

## Evidence and limits

- V6.3 same-seed full run #38330672815: 10/30, Wilson 95% interval 19.2%–51.2%; 11 empty trees and 3 premature empty outcomes; 0 scratch-file cases; 18/30 locator hits.
- V5 also scored 10/30 on the same task IDs. Paired results were 9 solved by both, 19 failed by both, and one solve unique to each version. V5 had 6 empty trees. These results do not establish a score winner.
- V6.3's instructions already set an edit-by-call-8 deadline, so the call-4 deadline is a targeted intervention, not a guaranteed improvement. V6.3 mini-screen #38329901183 was 0/4 and did not predict the full run.
- Run #38330672815's overall workflow conclusion was `failure` due to its commit-results step; the benchmark step itself succeeded, and its results were recovered by read-only fetch run #38347822030.

## Offline checks

`build_submission_v64.py` validates the exact package file set, the prompt/locator match, the tool-list intervention, unchanged model and budget settings, optional YAML parsing (when PyYAML is installed), ZIP contents, and CRC. It creates only the local deterministic archive. It does not start a benchmark or submit anything. The build was run twice with identical output.

- Archive SHA-256: `0cc04c08f16b3ee965bf449af5ed8599eb4b18876f593f98f01de82bec37d514`
- Archive contents: exactly five submission files (`agent.yaml`, `eval_config.yaml`, `configs/sampling.yaml`, `prompts/system.md`, `tools/locate.py`)
- `git diff --check`: passed; no files staged or committed.

A future same-task, same-seed evaluation would be needed to measure whether V6.4 reduces empty trees or affects solve rate. No benchmark trigger or submission request was created as part of this preparation.
