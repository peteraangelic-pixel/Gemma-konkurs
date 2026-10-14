Push-mechanism probe trigger (2026-10-14 03:20 UTC).

Question it answers: does `kaggle kernels push` create kernels on this account at all? Both V6.5 and
V6.6 recorded push_exit_code 0, but the kernels are absent from `kernels list --mine` and
`kernels status` answers 404 for both references.

What it pushes: a trivial CPU-only notebook (enable_gpu: false), so NO GPU quota is consumed and no
competition data is touched. It records the raw push output, the status after 45 s, the listing, and
the status of the two vanished benchmark kernels into
gemma4-agent/kaggle_results/v65v66-diagnostics/push-probe.txt.

No competition submission is created. The workflow deletes this file in its results commit.
