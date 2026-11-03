"""Wspólny limiter szybkości — 5 req/s to TWARDY limit regulaminu, nie sugestia.

Dlaczego plik, a nie zwykły threading.Lock: przy `multiprocessing` (Python FFI +
procesy, zgodnie z wymaganiem "wszędzie gdzie się da") licznik w pamięci każdego
procesu liczyłby osobno i suma przekroczyłaby 5 req/s. Token bucket trzymany
w pliku pod `fcntl.flock` jest wspólny dla wszystkich procesów na maszynie.

Odmowa startu przy `rps > 5` jest celowa: to jedyny błąd w narzędziach tego typu,
który unieważnia WSZYSTKIE nagrody naraz (regulamin §6 pkt 3).
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path

from .scope import MAX_RPS, SAFE_RPS


class RateConfigError(ValueError):
    pass


class TokenBucket:
    """Token bucket w pliku, bezpieczny między procesami.

    Domyślnie 4.5 req/s i burst = 4.5 (czyli ~1 s zapasu). `acquire()` blokuje.
    """

    def __init__(self, rps: float = SAFE_RPS, state_path: str | Path = None,
                 burst: float | None = None):
        if rps <= 0:
            raise RateConfigError("rps musi być > 0")
        if rps > MAX_RPS:
            raise RateConfigError(
                f"rps={rps} przekracza limit regulaminu {MAX_RPS} req/s — odmowa startu")
        self.rps = float(rps)
        self.burst = float(burst if burst is not None else max(1.0, rps))
        self.path = Path(state_path or os.environ.get(
            "NASK_RATE_STATE", "/tmp/nask-ratelimit.json"))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self, fh) -> dict:
        try:
            fh.seek(0)
            data = json.loads(fh.read() or "{}")
        except (json.JSONDecodeError, ValueError):
            data = {}
        now = time.time()
        tokens = float(data.get("tokens", self.burst))
        last = float(data.get("ts", now))
        tokens = min(self.burst, tokens + max(0.0, now - last) * self.rps)
        return {"tokens": tokens, "ts": now}

    def acquire(self, n: float = 1.0, timeout: float | None = None) -> float:
        """Zajmij n tokenów. Zwraca ile sekund czekaliśmy (do logów)."""
        deadline = None if timeout is None else time.time() + timeout
        waited = 0.0
        while True:
            with open(self.path, "a+") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)
                try:
                    state = self._read(fh)
                    if state["tokens"] >= n:
                        state["tokens"] -= n
                        fh.seek(0)
                        fh.truncate()
                        fh.write(json.dumps(state))
                        return waited
                    need = (n - state["tokens"]) / self.rps
                    # zapisz odświeżony stan, żeby inne procesy nie cofały zegara
                    fh.seek(0)
                    fh.truncate()
                    fh.write(json.dumps(state))
                finally:
                    fcntl.flock(fh, fcntl.LOCK_UN)
            if deadline is not None and time.time() + need > deadline:
                raise TimeoutError("limiter: przekroczono timeout oczekiwania")
            time.sleep(min(need, 0.25))
            waited += min(need, 0.25)


class Budget:
    """Twardy licznik żądań: po N żądaniach narzędzie staje, a nie 'próbuje dalej'."""

    def __init__(self, max_requests: int):
        if max_requests < 1:
            raise RateConfigError("budżet żądań musi być >= 1")
        self.max_requests = int(max_requests)
        self.used = 0

    @property
    def left(self) -> int:
        return self.max_requests - self.used

    def spend(self) -> None:
        if self.used >= self.max_requests:
            raise RuntimeError(
                f"budżet {self.max_requests} żądań wyczerpany — zatrzymano celowo")
        self.used += 1
