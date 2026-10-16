Arm the V7-c clock screen for the weekly GPU quota reset.

Pushing this file starts the workflow; its first step sleeps until the next 00:05 UTC (Saturday
2026-10-17, 02:05 Warsaw) - the weekly Kaggle GPU quota resets at 00:00 UTC and the daily
submission boundary is 00:05 UTC - and only then starts the kernel. Nothing consumes the expiring
week's quota, and nobody has to be awake at 2 a.m.

What it measures, and why only this: V7-c is the V5 archive with exactly ONE changed value,
max_time_minutes 5.25 -> 8.0 (agent.yaml, configs/sampling.yaml and prompts/system.md are
byte-identical to V5). The question is whether the MEAN task duration stays inside the
competition's 12-hour whole-run limit, because that limit covers the entire run and a breach
errors the WHOLE submission (host, discussion 743063). Safe targets: mean <= 4.3 min fits even a
150-task split, mean <= 5.5 min fits only ~120 tasks, above 5.5 min the clock stays at 5.25.

This is a measurement arm. It is never submitted to Kaggle as an official entry; the packer
refuses this clock outside the submission-v7c tree and prints a MEASUREMENT ARM banner.
Gates Z1-Z5 are pre-registered in gemma4-agent/GATES_V7_C.md.

Layout: the arm job starts the kernel and records its reference, the collect job (fresh 6-hour
budget) polls with gemma4-agent/tools/poll_kernel_until_done.py and commits the result. The raw
per-task patches are deleted before anything is persisted.
