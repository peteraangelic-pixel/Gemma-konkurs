V6.5 full 30-task benchmark - re-fire #2 (2026-10-14 03:45 UTC).

Why: run 38502671967 pushed the kernel at 02:45:22 (push_exit_code 0) and died at the status poll;
the kernel is not on Kaggle. Probe v2 proved the mechanism: two pushes fired 26 s apart produced two
addressable-less records (the two blank, untitled [Private Notebook] rows dated 2010-04-01, sitting
right where kernels created at 02:45 belong), while a single push with a title that slugifies to the
id resolves normally. So the kernels were never readable and no results exist from them.

Re-firing with the hardened tool, which now (a) keeps the raw push output in run.json,
(b) verifies 'KernelWorkerStatus' appears within two minutes or exits 6 instead of polling for four
hours, and (c) separates a 404 from a real API failure in the record.

No competition submission is created. The workflow deletes this file in its results commit.
