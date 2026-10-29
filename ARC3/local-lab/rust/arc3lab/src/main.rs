//! arc3lab - the 16-core harness for the ARC-AGI-3 local lab.
//!
//! Three jobs, none of which the Python lab can do well:
//!
//!  * `score`  - recompute the competition score from any saved `benchmark.json`, with the
//!               exact taaf/arc_agi rule, and diff it against what the harness itself wrote
//!               (a regression test that would have caught our own 32x scoring error).
//!  * `alloc`  - rank every (game, next level) pair by marginal points and greedily buy the
//!               cheapest path to a target mean. This is the token-allocation table: level k
//!               pays k units, so the next level of a 6-level game is worth more than two
//!               levels of an 9-level one.
//!  * `sweep`  - Rayon fan-out over games, one Python worker process per core (each worker
//!               drives the real engine, which is Python by construction), then aggregate.
//!               On a 5950X: `--workers 14` leaves two cores for vLLM.
//!
//! Build: `cargo build --release` (needs network for crates.io only).
//! Run:   `./target/release/arc3lab score ../../../../kaggle/ops/results/*/output*/benchmark.json`
//!
//! Design note: the engine step is Python and stays Python. Rayon parallelises *across
//! games and policies*, which is where the 16 cores actually pay: 25 games x 3 seeds is 75
//! independent processes, and the per-process cost is dominated by engine render, not by
//! anything Rust could absorb.

use rayon::prelude::*;
use serde::Deserialize;
use std::collections::BTreeMap;
use std::error::Error;
use std::fs;
use std::path::PathBuf;
use std::process::Command;

const LEVEL_CAP: f64 = 115.0; // points; = 1.15 x 100, applied per level
const COMPLETION_SCALE: f64 = 100.0;

// ---------------------------------------------------------------- scoring (taaf-exact)
pub fn level_score(baseline: f64, actions: f64) -> f64 {
    if actions <= 0.0 || baseline <= 0.0 {
        return 0.0;
    }
    let raw = (baseline / actions).powi(2) * 100.0;
    raw.min(LEVEL_CAP)
}

/// Exact re-implementation of `taaf.game.GameRun._compute_final_score`:
/// `min(sum(level*weight)/sum(weights), 100*sum(scored weights)/sum(weights))`.
///
/// The second term is the completion cap and it is easy to miss: efficiency better than
/// baseline cannot lift a game above the 100-point scale that clearing k of n levels
/// allows. Getting this wrong (or crediting the level currently being ground) is how a
/// 0.35 came out as 11.30 in our first analyser.
pub fn game_score(actions: &[i64], base: &[i64], levels_completed: i64) -> f64 {
    let n = base.len();
    if n == 0 {
        return 0.0;
    }
    let done = levels_completed.clamp(0, n as i64) as usize;
    let mut total = 0.0f64;
    let mut total_w = 0.0f64;
    let mut scored_w = 0.0f64;
    for i in 0..n {
        let w = (i + 1) as f64;
        total_w += w;
        let acts = *actions.get(i).unwrap_or(&0);
        let ls = if i < done { level_score(base[i] as f64, acts as f64) } else { 0.0 };
        if ls > 0.0 {
            scored_w += w;
        }
        total += ls * w;
    }
    if total_w == 0.0 {
        return 0.0;
    }
    (total / total_w).min(COMPLETION_SCALE * scored_w / total_w)
}

/// Points the next level is worth if cleared at baseline efficiency: 100 * k / sum(1..n).
pub fn next_level_value(base: &[i64], level_index_zero_based: usize) -> f64 {
    let n = base.len();
    if n == 0 || level_index_zero_based >= n {
        return 0.0;
    }
    let total_w: f64 = (1..=n).map(|k| k as f64).sum();
    COMPLETION_SCALE * (level_index_zero_based + 1) as f64 / total_w
}

// ---------------------------------------------------------------- benchmark.json model
#[derive(Debug, Deserialize)]
struct BenchFile {
    #[serde(default)]
    game_runs: Vec<RunRow>,
}

#[derive(Debug, Clone, Deserialize)]
struct RunRow {
    game_id: String,
    #[serde(default)]
    base_actions_per_level: Vec<i64>,
    #[serde(default)]
    actions_per_level: Vec<i64>,
    #[serde(default)]
    levels_completed: i64,
    #[serde(default)]
    final_score: Option<f64>,
    #[serde(default)]
    state: Option<String>,
    #[serde(default)]
    final_generated_tokens: Option<f64>,
    #[serde(default)]
    final_wallclock_seconds: Option<f64>,
    #[serde(default)]
    history: Vec<HistRow>,
}

#[derive(Debug, Clone, Deserialize)]
struct HistRow {
    #[serde(default)]
    generated_tokens: f64,
}

impl RunRow {
    fn tokens(&self) -> f64 {
        self.final_generated_tokens
            .unwrap_or_else(|| self.history.iter().map(|h| h.generated_tokens).sum())
    }
    fn score(&self) -> f64 {
        game_score(&self.actions_per_level, &self.base_actions_per_level, self.levels_completed)
    }
    fn n(&self) -> usize {
        self.base_actions_per_level.len()
    }
    /// Observed efficiency on cleared levels (baseline/actions); 1.0 = exactly baseline.
    fn median_eff(&self) -> Option<f64> {
        let mut v: Vec<f64> = (0..self.levels_completed.min(self.actions_per_level.len() as i64) as usize)
            .filter(|&i| self.actions_per_level[i] > 0 && self.base_actions_per_level[i] > 0)
            .map(|i| self.base_actions_per_level[i] as f64 / self.actions_per_level[i] as f64)
            .collect();
        if v.is_empty() {
            return None;
        }
        v.sort_by(|a, b| a.partial_cmp(b).unwrap());
        Some(v[v.len() / 2])
    }
}

fn load_runs(path: &PathBuf) -> Result<Vec<RunRow>, Box<dyn Error>> {
    let txt = fs::read_to_string(path)?;
    let parsed: BenchFile = serde_json::from_str(&txt)?;
    Ok(parsed.game_runs)
}

// ---------------------------------------------------------------- score
fn cmd_score(paths: &[PathBuf]) -> Result<(), Box<dyn Error>> {
    let mut all: Vec<(String, RunRow)> = Vec::new();
    for p in paths {
        for r in load_runs(p)? {
            all.push((p.display().to_string(), r));
        }
    }
    if all.is_empty() {
        println!("no game_runs found in {} file(s)", paths.len());
        return Ok(());
    }
    println!("{:16}{:>8}{:>8}{:>9}{:>10}  verdict", "game", "levels", "ours", "harness", "diff");
    let mut max_diff = 0.0f64;
    let mut bad = 0usize;
    let mut sums: BTreeMap<String, (f64, usize)> = BTreeMap::new();
    for (path, r) in &all {
        let ours = r.score();
        let theirs = r.final_score;
        let diff = theirs.map(|t| (t - ours).abs()).unwrap_or(0.0);
        max_diff = max_diff.max(diff);
        let verdict = match theirs {
            None => "no stored score".to_string(),
            Some(_) if diff < 1e-3 => "ok".to_string(),
            Some(t) => {
                bad += 1;
                format!("MISMATCH (harness {:.3})", t)
            }
        };
        let e = sums.entry(path.clone()).or_insert((0.0, 0));
        e.0 += ours;
        e.1 += 1;
        println!(
            "{:16}{:>8}{:>8.2}{:>9}{:>10.4}  {}",
            short(&r.game_id),
            format!("{}/{}", r.levels_completed, r.n()),
            ours,
            theirs.map(|t| format!("{:.2}", t)).unwrap_or_else(|| "-".into()),
            diff,
            verdict
        );
    }
    println!("\nmax |diff| = {:.4}, mismatches = {}", max_diff, bad);
    for (path, (sum, n)) in sums {
        println!("mean over {:2} games = {:6.2}   {}", n, sum / n as f64, path);
    }
    Ok(())
}

// ---------------------------------------------------------------- alloc
fn cmd_alloc(paths: &[PathBuf], target: f64) -> Result<(), Box<dyn Error>> {
    for p in paths {
        let mut runs = load_runs(p)?;
        if runs.is_empty() {
            continue;
        }
        println!("\n=== {} ({} games)", p.display(), runs.len());
        let n_games = runs.len() as f64;
        let mean: f64 = runs.iter().map(|r| r.score()).sum::<f64>() / n_games;

        // marginal value of the next level, in parallel: this is the only place the
        // ranking is expensive enough to matter on 110 games.
        let next: Vec<f64> = runs
            .par_iter()
            .map(|r| next_level_value(&r.base_actions_per_level, r.levels_completed.max(0) as usize))
            .collect();

        println!("{:16}{:>8}{:>8}{:>7}{:>8}{:>9}  state", "game", "levels", "score", "next", "eff", "tokens");
        let mut order: Vec<usize> = (0..runs.len()).collect();
        order.sort_by(|&a, &b| next[b].partial_cmp(&next[a]).unwrap());
        for &i in &order {
            let r = &runs[i];
            println!(
                "{:16}{:>8}{:>8.2}{:>7.2}{:>8}{:>9.0}  {}",
                short(&r.game_id),
                format!("{}/{}", r.levels_completed, r.n()),
                r.score(),
                next[i],
                r.median_eff().map(|e| format!("{:.2}", e)).unwrap_or_else(|| "-".into()),
                r.tokens(),
                r.state.clone().unwrap_or_default()
            );
        }
        println!("mean = {:.2}; to reach {:.0} needs +{:.2}", mean, target, target - mean);
        if target - mean > 0.0 {
            let mut depth: Vec<i64> = runs.iter().map(|r| r.levels_completed).collect();
            let mut marg: Vec<f64> = next.clone();
            let mut projected = mean;
            let mut bought = 0;
            while projected < target && bought < 1000 {
                let mut best = None;
                let mut best_v = 0.0f64;
                for i in 0..runs.len() {
                    let n = runs[i].n() as i64;
                    if depth[i] < n && marg[i] > best_v {
                        best_v = marg[i];
                        best = Some(i);
                    }
                }
                let Some(i) = best else { break };
                depth[i] += 1;
                projected += best_v / n_games;
                println!(
                    "  buy {:16} -> level {}/{}  worth {:5.2}  running mean {:5.2}",
                    short(&runs[i].game_id), depth[i], runs[i].n(), best_v, projected
                );
                marg[i] = next_level_value(&runs[i].base_actions_per_level, depth[i] as usize);
                bought += 1;
            }
            println!("  => {} extra levels, projected mean {:.2}", bought, projected);
        }
        // efficiency sensitivity: same depth, same throttle factor on every level
        let actual = mean;
        print!("\n  throttle sensitivity (same levels cleared): ");
        for ratio in [0.5, 1.0, 1.5, 2.0, 3.0] {
            let s: f64 = runs
                .par_iter()
                .map(|r| {
                    let k = r.levels_completed.max(0) as usize;
                    let acts: Vec<i64> = (0..k)
                        .map(|i| ((r.base_actions_per_level[i] as f64) * ratio).round().max(1.0) as i64)
                        .collect();
                    game_score(&acts, &r.base_actions_per_level, r.levels_completed)
                })
                .sum::<f64>()
                / n_games;
            print!("x{:.1} -> {:.2} ({:+.2})  ", ratio, s, s - actual);
        }
        println!();
    }
    Ok(())
}

// ---------------------------------------------------------------- sweep
#[derive(Debug, Deserialize)]
struct WorkerOut {
    game: String,
    levels: i64,
    #[serde(default)]
    levels_total: Option<i64>,
    #[serde(default)]
    actions: i64,
    #[serde(default)]
    actions_per_level: Vec<i64>,
    #[serde(default)]
    baseline: Option<Vec<i64>>,
    #[serde(default)]
    score: f64,
    #[serde(default)]
    clone_policy: Option<String>,
    #[serde(default)]
    node_ms: Option<f64>,
    #[serde(default)]
    nodes_per_s: Option<f64>,
    #[serde(default)]
    secs: Option<f64>,
}

fn run_worker(
    python: &str,
    worker: &PathBuf,
    game: &str,
    levels: i64,
    nodes: i64,
    time_s: f64,
    seed: i64,
) -> Result<WorkerOut, String> {
    let out = Command::new(python)
        .arg(worker)
        .arg("--game")
        .arg(game)
        .arg("--levels")
        .arg(levels.to_string())
        .arg("--nodes")
        .arg(nodes.to_string())
        .arg("--time-s")
        .arg(time_s.to_string())
        .arg("--seed")
        .arg(seed.to_string())
        .output()
        .map_err(|e| format!("{}: spawn failed: {}", game, e))?;
    if !out.status.success() {
        return Err(format!(
            "{}: exit {:?}: {}",
            game,
            out.status.code(),
            String::from_utf8_lossy(&out.stderr).lines().rev().take(3).collect::<Vec<_>>().join(" | ")
        ));
    }
    let text = String::from_utf8_lossy(&out.stdout);
    let line = text
        .lines()
        .rev()
        .find(|l| l.trim_start().starts_with('{'))
        .ok_or_else(|| format!("{}: no JSON on stdout", game))?;
    serde_json::from_str(line).map_err(|e| format!("{}: bad JSON: {}", game, e))
}

fn cmd_sweep(
    games: &[String],
    levels: i64,
    nodes: i64,
    time_s: f64,
    seeds: i64,
    python: &str,
    worker: &PathBuf,
    threads: usize,
    json_out: Option<&PathBuf>,
) -> Result<(), Box<dyn Error>> {
    let mut jobs: Vec<(String, i64)> = Vec::new();
    for g in games {
        for s in 0..seeds {
            jobs.push((g.clone(), s));
        }
    }
    println!("{} jobs ({} games x {} seeds) on {} threads", jobs.len(), games.len(), seeds, threads);

    let pool = rayon::ThreadPoolBuilder::new().num_threads(threads).build()?;
    let results: Vec<Result<WorkerOut, String>> = pool.install(|| {
        jobs.par_iter()
            .map(|(g, s)| run_worker(python, worker, g, levels, nodes, time_s, *s))
            .collect()
    });

    let mut rows: Vec<WorkerOut> = Vec::new();
    let mut errors = 0usize;
    for r in results {
        match r {
            Ok(v) => rows.push(v),
            Err(e) => {
                errors += 1;
                eprintln!("ERR {}", e);
            }
        }
    }

    // per-game best over seeds: this is what the scorecard does per environment
    let mut best: BTreeMap<String, &WorkerOut> = BTreeMap::new();
    for r in &rows {
        best.entry(r.game.clone())
            .and_modify(|b| {
                if r.levels > b.levels {
                    *b = r;
                }
            })
            .or_insert(r);
    }

    println!("\n{:10}{:>7}{:>9}{:>8}{:>8}{:>9}  policy", "game", "levels", "actions", "score", "n/s", "secs");
    let mut total = 0.0f64;
    let mut levels_total = 0i64;
    for (g, r) in &best {
        total += r.score;
        levels_total += r.levels;
        println!(
            "{:10}{:>7}{:>9}{:>8.2}{:>8}{:>9}  {}",
            g,
            format!("{}/{}", r.levels, r.levels_total.unwrap_or(-1)),
            r.actions,
            r.score,
            r.nodes_per_s.map(|v| format!("{:.0}", v)).unwrap_or_else(|| "-".into()),
            r.secs.map(|v| format!("{:.0}", v)).unwrap_or_else(|| "-".into()),
            r.clone_policy.clone().unwrap_or_default()
        );
    }
    println!(
        "\nmean best-per-game score = {:.2} over {} games | {} levels | {} errors",
        total / best.len().max(1) as f64,
        best.len(),
        levels_total,
        errors
    );

    if let Some(p) = json_out {
        let doc = serde_json::json!({
            "mean_score": total / best.len().max(1) as f64,
            "levels_total": levels_total,
            "errors": errors,
            "rows": rows.iter().map(|r| serde_json::json!({
                "game": r.game, "levels": r.levels, "levels_total": r.levels_total,
                "actions": r.actions, "actions_per_level": r.actions_per_level,
                "baseline": r.baseline, "score": r.score,
                "clone_policy": r.clone_policy, "node_ms": r.node_ms,
                "nodes_per_s": r.nodes_per_s, "secs": r.secs,
            })).collect::<Vec<_>>(),
        });
        fs::write(p, serde_json::to_string_pretty(&doc)?)?;
        println!("written {}", p.display());
    }
    if errors > 0 {
        return Err(format!("{} worker(s) failed", errors).into());
    }
    Ok(())
}

fn short(game_id: &str) -> String {
    game_id.split('-').next().unwrap_or(game_id).to_string()
}

// ---------------------------------------------------------------- cli
fn usage() -> &'static str {
    "arc3lab - ARC-AGI-3 local lab harness (16 cores)

USAGE:
  arc3lab score <benchmark.json>...            recompute the score, diff vs harness
  arc3lab alloc <benchmark.json>... [--target 50]
                                               rank marginal levels, buy to target
  arc3lab sweep --games cn04,ls20 --levels 2 --nodes 4000 --time-s 120 --seeds 3
                [--threads 14] [--python python3] [--worker ../worker.py] [--json out.json]

The engine is Python: `sweep` fans out one worker process per job across Rayon threads."
}

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {}", e);
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        println!("{}", usage());
        return Ok(());
    }
    let cmd = args[0].clone();
    let mut files: Vec<PathBuf> = Vec::new();
    let mut target = 50.0f64;
    let mut games: Vec<String> = Vec::new();
    let mut levels = 2i64;
    let mut nodes = 4000i64;
    let mut time_s = 120.0f64;
    let mut seeds = 1i64;
    let mut threads = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4);
    let mut python = "python3".to_string();
    let mut worker = PathBuf::from("../worker.py");
    let mut json_out: Option<PathBuf> = None;

    let mut i = 1;
    while i < args.len() {
        let a = args[i].clone();
        let mut next = |i: &mut usize| -> String {
            *i += 1;
            args.get(*i).cloned().unwrap_or_default()
        };
        match a.as_str() {
            "--target" => target = next(&mut i).parse()?,
            "--games" => games = next(&mut i).split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect(),
            "--levels" => levels = next(&mut i).parse()?,
            "--nodes" => nodes = next(&mut i).parse()?,
            "--time-s" => time_s = next(&mut i).parse()?,
            "--seeds" => seeds = next(&mut i).parse()?,
            "--threads" => threads = next(&mut i).parse()?,
            "--python" => python = next(&mut i),
            "--worker" => worker = PathBuf::from(next(&mut i)),
            "--json" => json_out = Some(PathBuf::from(next(&mut i))),
            "-h" | "--help" => {
                println!("{}", usage());
                return Ok(());
            }
            other if other.starts_with("--") => return Err(format!("unknown flag {}", other).into()),
            other => files.push(PathBuf::from(other)),
        }
        i += 1;
    }

    match cmd.as_str() {
        "score" => cmd_score(&files),
        "alloc" => cmd_alloc(&files, target),
        "sweep" => {
            if games.is_empty() {
                return Err("sweep needs --games (comma separated) ".into());
            }
            cmd_sweep(&games, levels, nodes, time_s, seeds, &python, &worker, threads, json_out.as_ref())
        }
        other => Err(format!("unknown command {:?}\n{}", other, usage()).into()),
    }
}

// ---------------------------------------------------------------- tests
#[cfg(test)]
mod tests {
    use super::*;

    // Every case below is a real (actions, baselines, levels, harness final_score) tuple
    // read out of the Smak repo's saved benchmark.json files. These are the cases that
    // caught our own 32x error, so they stay in the test suite.
    #[test]
    fn reproduces_harness_final_score() {
        // r093 cn04: 1/6 levels, 14 actions vs 29 baseline -> the completion cap bites
        assert!((game_score(&[14, 57], &[29, 54, 85, 300, 208, 113], 1) - 4.762).abs() < 1e-3);
        // r085 m0r0: 4/6 levels, efficiency above baseline throughout
        assert!((game_score(&[22, 41, 94, 31, 64], &[30, 111, 203, 26, 500, 237], 4) - 46.256).abs() < 1e-3);
        // r085 cn04: 5/6
        assert!((game_score(&[35, 30, 25, 41, 52, 5], &[29, 54, 85, 300, 208, 113], 5) - 71.429).abs() < 1e-3);
        // r085 ls20: 3/7, one brutal level (222 actions vs 73)
        assert!((game_score(&[17, 175, 222, 13], &[22, 123, 73, 84, 96, 192, 186], 3) - 8.794).abs() < 1e-3);
        // r110 su15: 1/9, better than baseline but capped at the 100 scale
        assert!((game_score(&[20, 36], &[22, 42, 26, 115, 36, 31, 8, 40, 41], 1) - 2.222).abs() < 1e-3);
    }

    #[test]
    fn partial_level_is_never_credited() {
        // the level currently being ground has an actions entry but is not completed
        let base = [29, 54, 85, 300, 208, 113];
        let with_partial = game_score(&[107, 47], &base, 0);
        assert_eq!(with_partial, 0.0);
    }

    #[test]
    fn full_depth_is_one_hundred() {
        let base = [10, 20, 30];
        assert!((game_score(&[10, 20, 30], &base, 3) - 100.0).abs() < 1e-9);
    }

    #[test]
    fn next_level_value_is_weight_share() {
        let base = [10, 10, 10, 10, 10, 10]; // total weight 21
        assert!((next_level_value(&base, 0) - 100.0 / 21.0).abs() < 1e-9);
        assert!((next_level_value(&base, 5) - 600.0 / 21.0).abs() < 1e-9);
        assert_eq!(next_level_value(&base, 6), 0.0);
    }

    #[test]
    fn effective_action_num() {
        // 2x slower on every level costs 3/4 of the points on those levels
        let base = [10, 10];
        let fast = game_score(&[10, 10], &base, 2);
        let slow = game_score(&[20, 20], &base, 2);
        assert!((fast - 100.0).abs() < 1e-9);
        assert!((slow - 25.0).abs() < 1e-9);
    }
}
