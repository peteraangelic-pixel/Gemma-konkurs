# arc3lab — Rust + Rayon harness

**Status: source only, not compiled here.** This sandbox has no Rust toolchain (`cargo`
and `rustc` are absent, only `gcc`), and you asked for something that runs on your 5950X.
So this is written to build there:

```bash
cd ARC3/local-lab/rust/arc3lab
cargo build --release          # ~30 s, needs crates.io for rayon/serde only
cargo test                     # 5 tests, all real numbers from saved benchmark.json files
```

If `cargo` complains about anything, the Python lab covers the same ground without it:
`verify_scoring.py` (scoring regression), `analyze_run.py` (equivalent of `score`+`alloc`),
`run_lab.py` (equivalent of `sweep`, using `multiprocessing`). The Rust binary is the
nicer, faster driver — it is not a prerequisite for any conclusion in `PLAN-50.md`.

## What it does

| command | what it is for |
|---|---|
| `arc3lab score <benchmark.json>...` | Recompute the competition score from any saved run and diff it against the harness's own `final_score`. This is a regression test for the scoring rule: it is what caught our 32× error. |
| `arc3lab alloc <benchmark.json> --target 50` | Rank every (game, next level) pair by marginal points, then greedily buy the cheapest path to the target. This is the token-allocation table for the next run. |
| `arc3lab sweep --games cn04,ls20 --levels 2 --seeds 3 --threads 14` | Rayon fan-out over (game × seed), one Python worker per job, then per-game best-of-seeds aggregation — the same "best run per environment" rule the scorecard uses. |

## Why Rayon and not a Rust engine

The 25 environments are Python source (`games/environment_files/<gid>/<gid>/<gid>.py`); there
is nothing to rewrite. Measured on this sandbox: engine step 0.07–2.9 ms, snapshot 0.5–8.6 ms,
so a worker loop is 95–1400 nodes/s and the bottleneck is the game's own `step()` plus
`camera.render()`. Rayon's job is therefore *across* games and seeds: 25 games × 3 seeds = 75
independent processes on 14 threads, with the aggregation and scoring done once, in Rust,
deterministically.

Memory: each worker holds one game object (a few MB after the fast-clone policies in
`lab/fastclone.py`); 14 workers on 64 GB is not a concern. Two cores are deliberately left
free so a vLLM/SGLang instance can run beside a sweep.

## Example session on the 5950X

```bash
# 1. correctness first: does our scoring reproduce every saved run?
./target/release/arc3lab score ~/smak/arc-agi-3/kaggle/ops/results/*/output*/benchmark.json

# 2. what is the next level worth, and what does 50 cost?
./target/release/arc3lab alloc ~/smak/arc-agi-3/kaggle/ops/results/r085-*/output*/benchmark.json --target 50

# 3. how many levels does the deterministic searcher get for free, and at what cost?
./target/release/arc3lab sweep --games all --levels 3 --nodes 8000 --time-s 240 \
    --seeds 2 --threads 14 --python python3 --worker ../../worker.py --json ../../results/sweep.json
```

`--games all` is not a magic word in the binary: pass the explicit list, or use the shell:

```bash
GAMES=$(ls ~/smak/arc-agi-3/games/environment_files | tr '\n' ',' | sed 's/,$//')
./target/release/arc3lab sweep --games "$GAMES" --threads 14
```
