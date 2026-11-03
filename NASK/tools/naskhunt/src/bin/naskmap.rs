//! `naskmap` — mapowanie API z publicznych bundle'i JS (offline po pobraniu).
//!
//! Przebieg: strona główna → lista `<script src>` → pobranie skryptów (limit, tempo) →
//! ekstrakcja ścieżek `/api/...`, wywołań `fetch(...)` i wzorców sekretów **lokalnie**.
//!
//! Po co: w aplikacjach SPA (Next.js) prawdziwa mapa endpointów nie jest w HTML-u, tylko
//! w chunkach JS. Bez tej mapy testowanie uprawnień to zgadywanie ścieżek.
//!
//! Zasady: wyłącznie hosty z `scope.json`, ≤ 2 req/s, cap liczby skryptów, zero POST-ów.

use nasktriage::scope::Scope;
use regex::Regex;
use std::collections::{BTreeMap, BTreeSet};
use std::time::{Duration, Instant};

struct Fetcher {
    agent: ureq::Agent,
    interval: Duration,
    last: Option<Instant>,
    scope: Scope,
    sent: usize,
    bytes: usize,
}

impl Fetcher {
    fn new(scope: Scope, rps: f64) -> Fetcher {
        let agent = ureq::AgentBuilder::new()
            .timeout_connect(Duration::from_secs(15))
            .timeout_read(Duration::from_secs(30))
            .redirects(0)
            .user_agent(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) \
                 Chrome/124.0 Safari/537.36 naskmap/0.1 (bug bounty hack.cert.pl)",
            )
            .build();
        Fetcher {
            agent,
            interval: Duration::from_secs_f64(1.0 / rps),
            last: None,
            scope,
            sent: 0,
            bytes: 0,
        }
    }

    fn get(&mut self, url: &str) -> Option<(u16, String, String)> {
        if self.scope.check_url(url).is_err() {
            return None;
        }
        if let Some(prev) = self.last {
            let e = prev.elapsed();
            if e < self.interval {
                std::thread::sleep(self.interval - e);
            }
        }
        self.last = Some(Instant::now());
        self.sent += 1;
        let out = match self.agent.get(url).call() {
            Ok(r) => {
                let st = r.status();
                let loc = r.header("location").unwrap_or("").to_string();
                let body = r.into_string().unwrap_or_default();
                (st, loc, body)
            }
            Err(ureq::Error::Status(code, r)) => {
                let loc = r.header("location").unwrap_or("").to_string();
                (code, loc, r.into_string().unwrap_or_default())
            }
            Err(e) => {
                eprintln!("  ! {url}: {e}");
                (0, String::new(), String::new())
            }
        };
        self.bytes += out.2.len();
        Some(out)
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let host_list: String = args
        .iter()
        .position(|a| a == "--hosts")
        .and_then(|i| args.get(i + 1))
        .cloned()
        .unwrap_or_default();
    let scope_path = args
        .iter()
        .position(|a| a == "--scope")
        .and_then(|i| args.get(i + 1))
        .cloned()
        .unwrap_or_else(|| "scope.example.json".to_string());
    let out = args
        .iter()
        .position(|a| a == "--md")
        .and_then(|i| args.get(i + 1))
        .cloned()
        .unwrap_or_else(|| "MAP.md".to_string());
    let max_scripts: usize = args
        .iter()
        .position(|a| a == "--max-scripts")
        .and_then(|i| args.get(i + 1))
        .and_then(|v| v.parse().ok())
        .unwrap_or(40);

    let scope = Scope::parse(&std::fs::read_to_string(&scope_path).expect("scope")).expect("scope");
    let mut f = Fetcher::new(scope, 2.0);

    let re_script = Regex::new(r#"(?:src|href)="([^"]+\.js[^"]*)""#).unwrap();
    let re_api = Regex::new(r#"/api/[A-Za-z0-9_\-./{}$:]{2,80}"#).unwrap();
    let re_path = Regex::new(r#""(/[a-z0-9][A-Za-z0-9_\-./]{2,60})""#).unwrap();
    let re_fetch = Regex::new(r#"fetch\(\s*[`"']([^`"']{2,120})"#).unwrap();
    let re_secret = Regex::new(
        r#"(?i)(api[_-]?key|secret[_-]?key|bearer\s+[A-Za-z0-9._-]{16,}|sk_live|password\s*[:=]|token\s*[:=])"#,
    )
    .unwrap();

    let mut md = String::from("# Mapa API z publicznych bundle'i JS\n\n");
    md.push_str(
        "Pobrane ze stron publicznych (bez logowania). Ekstrakcja offline. \
         Ścieżki to **hipotezy do sprawdzenia**, nie podatności.\n\n",
    );

    for host in host_list.split(',').map(str::trim).filter(|h| !h.is_empty()) {
        let base = format!("https://{host}");
        md.push_str(&format!("## `{host}`\n\n"));
        let home = f.get(&format!("{base}/"));
        let (status, loc, html) = match home {
            Some(v) => v,
            None => {
                md.push_str("poza zakresem — pominięte\n\n");
                continue;
            }
        };
        md.push_str(&format!("- strona główna: **{status}**, {} B", html.len()));
        if !loc.is_empty() {
            md.push_str(&format!(", Location: `{loc}`"));
        }
        md.push('\n');
        if status == 0 {
            md.push_str("- brak połączenia z runnera (WAF/TLS) — ten host trzeba pobrać lokalnie\n\n");
            continue;
        }

        // skrypty: względne i absolutne, tylko ten sam host
        let mut scripts: BTreeSet<String> = BTreeSet::new();
        for cap in re_script.captures_iter(&html) {
            let src = cap[1].to_string();
            if src.starts_with("http") {
                if src.contains(host) {
                    scripts.insert(src);
                }
            } else if src.starts_with('/') {
                scripts.insert(format!("{base}{src}"));
            }
        }
        md.push_str(&format!("- skryptów znalezionych: **{}** (pobieram max {max_scripts})\n\n", scripts.len()));

        let mut apis: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
        let mut fetches: BTreeSet<String> = BTreeSet::new();
        let mut secrets: BTreeSet<String> = BTreeSet::new();
        let mut fetched = 0;

        for url in scripts.iter().take(max_scripts) {
            let Some((st, _, js)) = f.get(url) else { continue };
            if st == 0 || js.len() < 64 {
                continue;
            }
            fetched += 1;
            for m in re_api.find_iter(&js) {
                apis.entry(m.as_str().to_string()).or_default().insert(url.clone());
            }
            for cap in re_fetch.captures_iter(&js) {
                fetches.insert(cap[1].to_string());
            }
            for cap in re_path.captures_iter(&js) {
                let p = cap[1].to_string();
                if p.starts_with("/api") || p.starts_with("/_next/data") {
                    apis.entry(p).or_default().insert(url.clone());
                }
            }
            for cap in re_secret.find_iter(&js) {
                let line = cap.as_str().to_string();
                if line.len() > 12 {
                    secrets.insert(line);
                }
            }
        }

        md.push_str(&format!("- skryptów pobranych: **{fetched}**\n\n"));

        if apis.is_empty() {
            md.push_str("### Endpointy API\n\nBrak `/api/...` w bundle'ach (albo chunki ładowane leniwie).\n\n");
        } else {
            md.push_str(&format!("### Endpointy API ({})\n\n| ścieżka | wystąpień |\n|---|---:|\n", apis.len()));
            for (p, srcs) in &apis {
                md.push_str(&format!("| `{}` | {} |\n", p, srcs.len()));
            }
            md.push('\n');
        }

        if !fetches.is_empty() {
            md.push_str(&format!("### Argumenty `fetch(...)` ({})\n\n", fetches.len()));
            for v in fetches.iter().take(60) {
                md.push_str(&format!("- `{v}`\n"));
            }
            md.push('\n');
        }
        if !secrets.is_empty() {
            md.push_str("### Wzorce sekretów (do ręcznej oceny)\n\n");
            for v in secrets.iter().take(20) {
                md.push_str(&format!("- `{v}`\n"));
            }
            md.push_str("\n> Nazwa pola z „token” w JS to nie sekret. Sprawdzać wartość, nie słowo.\n\n");
        }
    }

    md.push_str(&format!(
        "\n---\nŻądań: **{}**, pobranych bajtów: **{}**.\n",
        f.sent, f.bytes
    ));
    std::fs::write(&out, &md).expect("zapis mapy");
    println!("{md}");
}
