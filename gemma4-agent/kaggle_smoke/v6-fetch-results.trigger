fetch results of the FINISHED V6.2 benchmark kernel (no GPU work, no Kaggle compute)
reason: the V6.2 benchmark completed (job step "Run private same-seed 30-task V6 benchmark" = success) but the "Commit V6 benchmark summary" step failed, so the results never reached the branch
kernel: matched by slug prefix gemma-agent-benchmark-8c1ea5b7 (first 8 hex of the V6.2 archive SHA-256)
archive: gemma4-agent/submission-v6.zip
archive_sha256: 8c1ea5b71a61b4d58a6b023596761abb9af37908af6d0ef441347353a2f860b8
operation: kaggle kernels output (read-only download of files the kernel already produced)
official_submission: false
expects: agent_benchmark_result.json + run.json with submission_sha256 == 8c1ea5b7..., resolved_count, localization_hits, tasks_with_empty_patch, per-task touched_files
