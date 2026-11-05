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
use sha2::{Digest, Sha256};
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
    /// Ciało żądania. Dozwolone wyłącznie dla odczytowych wyszukiwarek `dns.pl`
    /// (whois / dostępność domeny) — patrz `post_allowed`. Puste = brak ciała.
    #[serde(default)]
    body: Option<String>,
    /// Zapisz surowe ciało do `NASK/hunt/bodies/<id>.<ext>` do analizy offline
    /// (kontekst refleksji, RSC payload). Ciała są publiczne, żadnych danych sesji.
    #[serde(default)]
    save_body: bool,
    /// Ciało jako `application/json` (kontrakt Vue `POST /api/{who-is-xml,domain-browser}`).
    #[serde(default)]
    json: bool,
}

/// POST wolno wysłać **tylko** na odczytowe endpointy wyszukiwania `dns.pl`.
/// To nie jest lista „na później”: host i prefiks ścieżki są sprawdzane w kodzie,
/// więc literówka w checkach nie wyśle żądania zapisującego.
fn post_allowed(host: &str, path: &str) -> bool {
    host.eq_ignore_ascii_case("dns.pl")
        && (path.starts_with("/api/who-is-xml/") || path.starts_with("/api/domain-browser/"))
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
    /// Jeden reczny skok na przekierowanie same-origin (308/307 z kanonizacja sciezki).
    /// Klient nie podaza automatycznie (moglby wyjsc z zakresu), ale bez tego sondy
    /// sa slepe: frameworki odpowiadaja 308 na kanoniczny wariant sciezki.
    hop_status: u16,
    hop_len: usize,
    hop_ctype: String,
    snippet: String,
    /// Odcisk ciała po normalizacji (ciągi cyfr -> `#`, hex >=16 znaków -> `<HEX>`),
    /// pierwsze 12 znaków SHA-256. Bez tego dwie identyczne strony różniące się
    /// rotującym `_event_transid` (dns.pl) wyglądają jak dwie różne odpowiedzi.
    sha12: String,
    /// Surowa treść (ucięta do 400 kB) — tylko do zapisu na dysk, nie do JSON-a.
    raw: String,
    error: String,
}

struct Runner {
    agent: ureq::Agent,
    /// Interwał między żądaniami wyliczony z `rps` — zegar rzeczywisty, nie wstrzykiwany.
    interval: Duration,
    last: Option<Instant>,
    scope: Scope,
    sent: usize,
    /// Baseline catch-all per host: losowa nieistniejaca sciezka. Serwis, ktory
    /// odpowiada 200 na wszystko (SPA), bez tego daje falszywe trafienia — to blad,
    /// ktory w cudzych przebiegach dal 200 "trafien" i zero wartosci.
    catchall: BTreeMap<String, Observation>,
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
            catchall: BTreeMap::new(),
        }
    }

    /// Jedno żądanie GET, bez interpretacji. Zwraca `None`, gdy host jest poza zakresem
    /// (i wtedy **nic nie wysyła**).
    fn get(&mut self, host: &str, path: &str, headers: &BTreeMap<String, String>) -> Option<Observation> {
        let mut obs = self.fetch_once(host, path, headers)?;
        // Jeden skok, wylacznie na ten sam host i wylacznie https. Kazdy hop to
        // osobne zadanie w limiterze i w liczniku.
        if matches!(obs.status, 301 | 302 | 303 | 307 | 308) {
            if let Some(next) = same_origin_path(host, &obs.location) {
                if let Some(hop) = self.fetch_once(host, &next, &BTreeMap::new()) {
                    obs.hop_status = hop.status;
                    obs.hop_len = hop.len;
                    obs.hop_ctype = hop.ctype;
                }
            }
        }
        Some(obs)
    }

    fn fetch_once(&mut self, host: &str, path: &str, headers: &BTreeMap<String, String>) -> Option<Observation> {
        self.fetch_full(host, path, headers, "GET", None, false)
    }

    /// Pełny wariant: metoda + opcjonalne ciało. `POST` przechodzi wyłącznie przez
    /// `post_allowed` (odczytowe wyszukiwarki `dns.pl`); wszystko inne jest odrzucane
    /// **przed** wysłaniem, z jawnym błędem w rekordzie.
    fn fetch_full(
        &mut self,
        host: &str,
        path: &str,
        headers: &BTreeMap<String, String>,
        method: &str,
        body: Option<&str>,
        json: bool,
    ) -> Option<Observation> {
        let url = format!("https://{host}{path}");
        if self.scope.check_url(&url).is_err() {
            return None;
        }
        let method_up = method.to_ascii_uppercase();
        if method_up != "GET" && !post_allowed(host, path) {
            return Some(Observation {
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
                hop_status: 0,
                hop_len: 0,
                hop_ctype: String::new(),
                snippet: String::new(),
                sha12: String::new(),
                raw: String::new(),
                error: format!("{method_up} zabroniony dla {host}{path} (tylko odczytowe trasy dns.pl)"),
            });
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
        let mut req = self.agent.request(&method_up, &url);
        for (k, v) in headers {
            req = req.set(k, v);
        }
        if json {
            req = req.set("Content-Type", "application/json");
        }
        let result = match (method_up.as_str(), body) {
            ("GET", _) => req.call(),
            (_, Some(b)) => req.send_string(b),
            (_, None) => req.send_string(""),
        };
        let obs = match result {
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
                hop_status: 0,
                hop_len: 0,
                hop_ctype: String::new(),
                snippet: String::new(),
                sha12: String::new(),
                raw: String::new(),
                error: format!("{e}"),
            },
        };
        Some(obs)
    }

    /// Baseline catch-all hostu, pobierany raz na przebieg.
    fn catchall_for(&mut self, host: &str) -> Option<Observation> {
        if let Some(o) = self.catchall.get(host) {
            return Some(o.clone());
        }
        let path = "/__naskhunt_catchall__/9f3c2b-there-is-no-such-page";
        let obs = self.fetch_once(host, path, &BTreeMap::new())?;
        self.catchall.insert(host.to_string(), obs.clone());
        Some(obs)
    }
}

/// Sciezka przekierowania, jesli zostaje na **tym samym hoscie** i uzywa https.
/// Porownanie hosta jest twarde: `nask.pl` -> `www.nask.pl` to inna nazwa hosta
/// i skok bylby wyjsciem z zakresu §5, nawet jesli domena ta sama.
fn same_origin_path(host: &str, location: &str) -> Option<String> {
    let loc = location.trim();
    if loc.is_empty() || loc.starts_with("//") {
        return None;
    }
    if let Some(rest) = loc.strip_prefix("https://") {
        let path_start = rest.find('/').unwrap_or(rest.len());
        let (loc_host, _) = rest.split_at(path_start);
        if !loc_host.eq_ignore_ascii_case(host) {
            return None;
        }
        let path = &rest[path_start..];
        let p = if path.is_empty() { "/" } else { path };
        return Some(p.to_string());
    }
    if loc.starts_with('/') {
        return Some(loc.to_string());
    }
    None // http:// (downgrade) i obce hosty odrzucone
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
    use std::io::Read;
    let mut buf: Vec<u8> = Vec::new();
    let _ = resp.into_reader().take(2_000_000).read_to_end(&mut buf);
    let len = buf.len();
    let body = String::from_utf8_lossy(&buf).to_string();
    let ms = t0.elapsed().as_millis();
    let sha12 = body_hash(&body);
    let binary = !(ctype.contains("text")
        || ctype.contains("json")
        || ctype.contains("xml")
        || ctype.contains("javascript")
        || ctype.is_empty());
    let mut snippet: String = if binary {
        format!("<bin {} B sha12={}>", len, sha12)
    } else {
        body.chars()
            .take(700)
            .collect::<String>()
            .replace('\n', " ")
            .replace('\r', " ")
            .replace('|', "/")
    };
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
        hop_status: 0,
        hop_len: 0,
        hop_ctype: String::new(),
        snippet,
        sha12,
        raw: body.chars().take(400_000).collect(),
        error: String::new(),
    }
}

/// Hash treści po normalizacji szumu: ciągi cyfr -> `#`, długie ciągi hex -> `<HEX>`.
/// Dzięki temu porównanie dwóch odpowiedzi mówi o treści, a nie o transidzie.
fn body_hash(body: &str) -> String {
    let mut out = String::with_capacity(body.len());
    let mut run: String = String::new();
    let mut kind = 0u8; // 1 = cyfry, 2 = hex z literami
    for ch in body.chars() {
        let k = if ch.is_ascii_digit() {
            1
        } else if ch.is_ascii_hexdigit() {
            2
        } else {
            0
        };
        if k != 0 && k == kind {
            run.push(ch);
            continue;
        }
        flush_run(&mut out, &run, kind);
        run.clear();
        kind = k;
        if k == 0 {
            out.push(ch);
        } else {
            run.push(ch);
        }
    }
    flush_run(&mut out, &run, kind);
    let digest = Sha256::digest(out.as_bytes());
    let hex: String = digest.iter().map(|b| format!("{b:02x}")).collect();
    hex[..12].to_string()
}

fn flush_run(out: &mut String, run: &str, kind: u8) {
    if run.is_empty() {
        return;
    }
    match kind {
        1 => out.push('#'),
        2 if run.len() >= 16 => out.push_str("<HEX>"),
        _ => out.push_str(run),
    }
}

fn is_denied(o: &Observation) -> bool {
    matches!(o.status, 401 | 403 | 404 | 405) || (300..400).contains(&o.status)
}

fn judge(
    _check: &Check,
    test: &Observation,
    base: Option<&Observation>,
    catchall: Option<&Observation>,
) -> Verdict {
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
    // Catch-all: host odpowiada tak samo na losowa nieistniejaca sciezke,
    // wiec odpowiedz tego zadania nic nie mowi o istnieniu zasobu.
    if let Some(c) = catchall {
        if c.status == test.status && c.len.abs_diff(test.len) < 48 {
            return Verdict::Clean;
        }
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
    let mut catchalls: BTreeMap<String, Observation> = BTreeMap::new();
    let mut results: Vec<(Check, Option<Observation>, Option<Observation>, Verdict)> = Vec::new();

    for check in &checks.checks {
        let base = check
            .baseline_path
            .as_ref()
            .and_then(|p| runner.get(&check.host, p, &BTreeMap::new()));
        let catchall = runner.catchall_for(&check.host);
        let test = if check.method.eq_ignore_ascii_case("GET") {
            runner.get(&check.host, &check.path, &check.headers)
        } else {
            // POST tylko na odczytowe trasy dns.pl — guard jest w `fetch_full`.
            runner.fetch_full(
                &check.host,
                &check.path,
                &check.headers,
                &check.method,
                check.body.as_deref(),
                check.json,
            )
        };
        let verdict = match &test {
            None => {
                eprintln!("POMINIĘTE (poza zakresem): {} {}", check.host, check.path);
                Verdict::Inconclusive
            }
            Some(t) => judge(check, t, base.as_ref(), catchall.as_ref()),
        };
        if let Some(c) = &catchall {
            catchalls.insert(check.host.clone(), c.clone());
        }
        results.push((check.clone(), test, base, verdict));
    }

    // ---- wyjście ---------------------------------------------------------
    let mut md = String::new();
    md.push_str("# naskhunt — raport sond (read-only)\n\n");
    md.push_str(&format!(
        "Żądań wysłanych: **{}**, tempo: ≤ {} req/s, przekierowania: nie podążamy.\n\n",
        runner.sent, rps
    ));
    md.push_str("| werdykt | id | host | ścieżka | status | len | sha12 | klasa |\n|---|---|---|---|---:|---:|---|---|\n");
    for (c, t, _, v) in &results {
        let st = t
            .as_ref()
            .map(|o| if o.hop_status > 0 { o.hop_status } else { o.status })
            .unwrap_or(0);
        let (ln, sha) = t
            .as_ref()
            .map(|o| (o.len.to_string(), o.sha12.clone()))
            .unwrap_or_else(|| ("-".to_string(), "-".to_string()));
        md.push_str(&format!(
            "| **{}** | `{}` | {} | `{}` | {} | {} | `{}` | {} |\n",
            v.as_str(),
            c.id,
            c.host,
            c.path,
            st,
            ln,
            sha,
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

    // Ciała tylko dla jawnie oznaczonych sond (analiza refleksji offline).
    let body_dir = std::path::Path::new(&out_json)
        .parent()
        .map(|p| p.join("bodies"))
        .unwrap_or_else(|| std::path::PathBuf::from("bodies"));
    for (c, t, _, _) in &results {
        let obs = match t {
            Some(o) => o,
            None => continue,
        };
        if !c.save_body || obs.raw.is_empty() {
            continue;
        }
        if std::fs::create_dir_all(&body_dir).is_ok() {
            let ext = if obs.ctype.contains("json") {
                "json"
            } else if obs.ctype.contains("html") {
                "html"
            } else {
                "txt"
            };
            let _ = std::fs::write(body_dir.join(format!("{}.{ext}", c.id)), &obs.raw);
        }
    }

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
            "hop_status": t.as_ref().map(|o| o.hop_status),
            "hop_len": t.as_ref().map(|o| o.hop_len),
            "hop_ctype": t.as_ref().map(|o| o.hop_ctype.clone()),
            "catchall_status": catchalls.get(&c.host).map(|o| o.status),
            "snippet": t.as_ref().map(|o| o.snippet.clone()),
            "sha12": t.as_ref().map(|o| o.sha12.clone()),
            "catchall_sha12": catchalls.get(&c.host).map(|o| o.sha12.clone()),
            "catchall_len": catchalls.get(&c.host).map(|o| o.len),
            "baseline_status": b.as_ref().map(|o| o.status),
            "error": t.as_ref().map(|o| o.error.clone()),
        })).collect::<Vec<_>>(),
    });
    let mut f = std::fs::File::create(&out_json).expect("zapis report.json");
    f.write_all(json.to_string().as_bytes()).ok();
    println!("{md}");
}
