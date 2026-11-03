//! `naskhunt` — kuratowane, read-only sondy dla programów hack.cert.pl.
//!
//! Zasady wpisane w kod, nie w komentarz:
//! * **zakres** — każde żądanie przechodzi przez `Scope::check_url`; host spoza §5 nie jest dotykany,
//! * **tempo** — wspólny `TokenBucket`, domyślnie 2 req/s, twardy sufit 5 req/s,
//! * **read-only** — tylko GET, bez ciał żądań, bez logowania, bez brute-force,
//! * **dowód** — każda sonda zapisuje status, długość, typ treści i wybrane nagłówki.
//!
//! Wejście: `checks.json` (audytowalna lista), `scope.example.json` (hosty z §5).
//! Wyjście: `report.md` + `report.json`.

use nasktriage::rate::TokenBucket;
use nasktriage::scope::Scope;
use serde::Deserialize;
use std::collections::BTreeMap;
use std::io::Write;
use std::time::{Duration, Instant};

#[derive(Debug, Deserialize)]
struct CheckFile {
    checks: Vec<Check>,
}

#[derive(Debug, Deserialize, Clone)]
struct Check {
    id: String,
    host: String,
    #[serde(default = "get")]
    method: String,
    path: String,
    #[serde(default)]
    headers: BTreeMap<String, String>,
    #[serde(default)]
    baseline_path: Option<String>,
    #[serde(default)]
    why: String,
    #[serde(default)]
    class: String,
}

fn get() -> String {
    "GET".to_string()
}

#[derive(Debug, Clone, PartialEq)]
enum Verdict {
    /// Odpowiedź różni się od baseline w sposób, który może być podatnością.
    Candidate,
    /// Odpowiedź wygląda na poprawną odmowę / brak zasobu.
    Clean,
    /// Nie da się rozstrzygnąć bez ręcznej analizy.
    Inconclusive,
}

impl Verdict {
    fn as_str(&self) -> &'static str {
        match self {
            Verdict::Candidate => "KANDYDAT",
            Verdict::Clean => "czysto",
            Verdict::Inconclusive => "niejednoznaczne",
        }
    }
}

#[derive(Debug, Clone)]
struct Observation {
    status: u16,
    len: usize,
    ctype: String,
    location: String,
    server: String,
    acao: String,
    acac: String,
    cdisp: String,
    clen: String,
    ms: u128,
    snippet: String,
    error: String,
}

struct Runner {
    agent: ureq::Agent,
    /// Interwał między żądaniami wyliczony z `rps` — zegar rzeczywisty, nie wstrzykiwany.
    interval: Duration,
    last: Option<Instant>,
    scope: Scope,
    sent: usize,
}

impl Runner {
    fn new(scope: Scope, rps: f64) -> Runner {
        let agent = ureq::AgentBuilder::new()
            .timeout_connect(Duration::from_secs(10))
            .timeout_read(Duration::from_secs(15))
            .redirects(0) // przekierowania notujemy, nie wykonujemy — inaczej wyjdziemy z zakresu
            .user_agent("naskhunt/0.1 (bug bounty hack.cert.pl; read-only; contact via platform)")
            .build();
        TokenBucket::new(rps).expect("rps w granicach regulaminu");
        Runner {
            agent,
            interval: Duration::from_secs_f64(1.0 / rps),
            last: None,
            scope,
            sent: 0,
        }
    }

    /// Jedno żądanie GET. Zwraca `None`, gdy host jest poza zakresem (i wtedy **nic nie wysyła**).
    fn get(&mut self, host: &str, path: &str, headers: &BTreeMap<String, String>) -> Option<Observation> {
        let url = format!("https://{host}{path}");
        if self.scope.check_url(&url).is_err() {
            return None;
        }
        if let Some(prev) = self.last {
            let elapsed = prev.elapsed();
            if elapsed < self.interval {
                std::thread::sleep(self.interval - elapsed);
            }
        }
        self.last = Some(Instant::now());
        self.sent += 1;

        let t0 = Instant::now();
        let mut req = self.agent.request(&"GET", &url);
        for (k, v) in headers {
            req = req.set(k, v);
        }
        let obs = match req.call() {
            Ok(resp) => read(resp, t0),
            Err(ureq::Error::Status(_, resp)) => read(resp, t0),
            Err(e) => Observation {
                status: 0,
                len: 0,
                ctype: String::new(),
                location: String::new(),
                server: String::new(),
                acao: String::new(),
                acac: String::new(),
                cdisp: String::new(),
                clen: String::new(),
                ms: 0,
                snippet: String::new(),
                error: format!("{e}"),
            },
        };
        Some(obs)
    }
}

fn read(resp: ureq::Response, t0: Instant) -> Observation {
    let status = resp.status();
    let hdr = |n: &str| resp.header(n).unwrap_or("").to_string();
    let ctype = hdr("content-type");
    let location = hdr("location");
    let server = hdr("server");
    let acao = hdr("access-control-allow-origin");
    let acac = hdr("access-control-allow-credentials");
    let cdisp = hdr("content-disposition");
    let clen = hdr("content-length");
    let body = resp.into_string().unwrap_or_default();
    let ms = t0.elapsed().as_millis();
    let len = body.len();
    let mut snippet: String = body
        .chars()
        .take(300)
        .collect::<String>()
        .replace('\n', " ")
        .replace('\r', " ")
        .replace('|', "/");
    while snippet.contains("  ") {
        snippet = snippet.replace("  ", " ");
    }
    Observation {
        status,
        len,
        ctype,
        location,
        server,
        acao,
        acac,
        cdisp,
        clen,
        ms,
        snippet,
        error: String::new(),
    }
}

fn is_denied(o: &Observation) -> bool {
    matches!(o.status, 401 | 403 | 404 | 405) || (300..400).contains(&o.status)
}

fn judge(check: &Check, test: &Observation, base: Option<&Observation>) -> Verdict {
    if test.status == 0 {
        return Verdict::Inconclusive;
    }
    if let Some(b) = base {
        // porównanie "z nagłówkiem" vs "bez nagłówka": różnica statusu na korzyść 200 = kandydat
        if (200..300).contains(&test.status) && is_denied(b) {
            return Verdict::Candidate;
        }
        if test.status == b.status && test.len.abs_diff(b.len) < 32 {
            return Verdict::Clean;
        }
    }
    let low = test.snippet.to_ascii_lowercase();
    if low.contains("not allowed") || low.contains("nie istnieje") || low.contains("\"message\"") {
        return Verdict::Clean;
    }
    // CORS: odbicie obcego Origin razem z credentials
    if test.acao.contains("arena-probe.example") && test.acac.eq_ignore_ascii_case("true") {
        return Verdict::Candidate;
    }
    // Uwaga: 200 + JSON to NIE podatność — publiczne API tak wyglądają.
    // Kandydata zgłaszamy tylko przy konkretnym sygnale, np. odbitym obcym Origin
    // (sprawdzone wyżej) albo różnicy względem baseline.
    if is_denied(test) {
        return Verdict::Clean;
    }
    Verdict::Inconclusive
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let get_arg = |name: &str, default: &str| -> String {
        args.iter()
            .position(|a| a == name)
            .and_then(|i| args.get(i + 1))
            .cloned()
            .unwrap_or_else(|| default.to_string())
    };
    let scope_path = get_arg("--scope", "scope.example.json");
    let checks_path = get_arg("--checks", "checks.json");
    let out_md = get_arg("--md", "report.md");
    let out_json = get_arg("--json", "report.json");
    let rps: f64 = get_arg("--rps", "2").parse().unwrap_or(2.0);

    let scope_text = std::fs::read_to_string(&scope_path).expect("scope.json");
    let scope = Scope::parse(&scope_text).expect("scope.json poprawny");
    if let Err(e) = TokenBucket::new(rps) {
        eprintln!("{e}");
        std::process::exit(2);
    }
    let checks: CheckFile = serde_json::from_str(
        &std::fs::read_to_string(&checks_path).expect("checks.json"),
    )
    .expect("checks.json poprawny");

    let mut runner = Runner::new(scope, rps);
    let mut results: Vec<(Check, Option<Observation>, Option<Observation>, Verdict)> = Vec::new();

    for check in &checks.checks {
        let base = check
            .baseline_path
            .as_ref()
            .and_then(|p| runner.get(&check.host, p, &BTreeMap::new()));
        let test = runner.get(&check.host, &check.path, &check.headers);
        let verdict = match &test {
            None => {
                eprintln!("POMINIĘTE (poza zakresem): {} {}", check.host, check.path);
                Verdict::Inconclusive
            }
            Some(t) => judge(check, t, base.as_ref()),
        };
        results.push((check.clone(), test, base, verdict));
    }

    // ---- wyjście ---------------------------------------------------------
    let mut md = String::new();
    md.push_str("# naskhunt — raport sond (read-only)\n\n");
    md.push_str(&format!(
        "Żądań wysłanych: **{}**, tempo: ≤ {} req/s, przekierowania: nie podążamy.\n\n",
        runner.sent, rps
    ));
    md.push_str("| werdykt | id | host | ścieżka | status | klasa |\n|---|---|---|---|---:|---|\n");
    for (c, t, _, v) in &results {
        let st = t.as_ref().map(|o| o.status).unwrap_or(0);
        md.push_str(&format!(
            "| **{}** | `{}` | {} | `{}` | {} | {} |\n",
            v.as_str(),
            c.id,
            c.host,
            c.path,
            st,
            c.class
        ));
    }

    md.push_str("\n## KANDYDACI — do ręcznego potwierdzenia\n\n");
    let mut any = false;
    for (c, t, b, v) in &results {
        if *v != Verdict::Candidate {
            continue;
        }
        any = true;
        md.push_str(&format!("### `{}` — {} {}{}\n\n", c.id, c.host, c.path, ""));
        md.push_str(&format!("- hipoteza: {}\n- klasa §8: {}\n", c.why, c.class));
        if let Some(t) = t {
            md.push_str(&format!(
                "- odpowiedź: **{}**, {} B, `{}`{}\n",
                t.status,
                t.len,
                t.ctype,
                if t.location.is_empty() {
                    String::new()
                } else {
                    format!(", Location: `{}`", t.location)
                }
            ));
            if !t.acao.is_empty() {
                md.push_str(&format!("- CORS: `{}` (credentials: `{}`)\n", t.acao, t.acac));
            }
            if !t.clen.is_empty() {
                md.push_str(&format!("- Content-Length: `{}`\n", t.clen));
            }
            if !t.cdisp.is_empty() {
                md.push_str(&format!("- Content-Disposition: `{}`\n", t.cdisp));
            }
            if !t.snippet.is_empty() {
                md.push_str(&format!("- początek treści: `{}`\n", t.snippet));
            }
        }
        if let Some(b) = b {
            md.push_str(&format!(
                "- baseline (bez nagłówka): {}, {} B\n",
                b.status, b.len
            ));
        }
        md.push_str("\n**Następny krok (ręcznie):** potwierdzić jednym żądaniem, ocenić wpływ, sprawdzić, czy klasa nie jest w wyłączeniach §8, napisać PoC.\n\n");
    }
    if !any {
        md.push_str("Brak. To też wynik — przy tych sondach nie ma czego potwierdzać.\n\n");
    }

    md.push_str("## Wszystkie obserwacje\n\n| id | status | ms | bajty | typ | Content-Disposition | snippet |\n|---|---:|---:|---:|---|---|---|\n");
    for (c, t, _, _) in &results {
        if let Some(t) = t {
            md.push_str(&format!(
                "| `{}` | {} | {} | {} | {} | `{}` | `{}` |\n",
                c.id, t.status, t.ms, t.len, t.ctype, t.cdisp, t.snippet
            ));
        }
    }
    md.push_str(
        "\n> Wszystkie sondy to pojedyncze GET-y. Narzędzie nie loguje się, nie wysyła ciał, \
         nie testuje obciążenia i nie podąża za przekierowaniami poza zakres.\n",
    );

    std::fs::write(&out_md, &md).expect("zapis report.md");
    let json = serde_json::json!({
        "tool": "naskhunt",
        "version": env!("CARGO_PKG_VERSION"),
        "requests_sent": runner.sent,
        "results": results.iter().map(|(c, t, b, v)| serde_json::json!({
            "id": c.id, "host": c.host, "path": c.path, "class": c.class,
            "verdict": v.as_str(),
            "status": t.as_ref().map(|o| o.status),
            "len": t.as_ref().map(|o| o.len),
            "ctype": t.as_ref().map(|o| o.ctype.clone()),
            "location": t.as_ref().map(|o| o.location.clone()),
            "acao": t.as_ref().map(|o| o.acao.clone()),
            "content_disposition": t.as_ref().map(|o| o.cdisp.clone()),
            "content_length_header": t.as_ref().map(|o| o.clen.clone()),
            "ms": t.as_ref().map(|o| o.ms),
            "snippet": t.as_ref().map(|o| o.snippet.clone()),
            "baseline_status": b.as_ref().map(|o| o.status),
            "error": t.as_ref().map(|o| o.error.clone()),
        })).collect::<Vec<_>>(),
    });
    let mut f = std::fs::File::create(&out_json).expect("zapis report.json");
    f.write_all(json.to_string().as_bytes()).ok();
    println!("{md}");
}
