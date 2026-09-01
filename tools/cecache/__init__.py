"""A cache and a rate limiter in front of the Compiler Explorer API.

Compiler Explorer is a free public service run by volunteers, and this project proposes to
put a teaching site on top of it. Two things follow from that.

The first is the cache. It is content addressed on everything that can change an answer,
which is the compiler id, the source, the argument string and the filters. It is meant to
be committed to the repository, because a cache that CI populates from a third party
service makes builds non reproducible and turns somebody else's outage into our build
failure.

The second is the limiter. It applies in the reader's browser as much as in CI. A minimum
interval between requests, and identical in flight requests coalesced rather than sent
twice.

CI never hits the live API at all. It populates the cache deliberately, through
`just ce-refresh`, and the `ce-parity` job then checks every cached response against the
local compiler. Fetching is a reviewed act that shows up as a diff in a pull request.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_STORE = Path(__file__).resolve().parent / "store"
DEFAULT_MIN_INTERVAL = 1.0


def request_key(compiler: str, source: str, args: str, filters: dict | None = None) -> str:
    """A stable id for one compilation. Everything that changes the answer is in here."""
    payload = json.dumps(
        {
            "compiler": compiler,
            "source": source,
            "args": args,
            "filters": filters or {},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


class RateLimiter:
    """A minimum interval between requests, shared across threads."""

    def __init__(self, min_interval: float = DEFAULT_MIN_INTERVAL):
        self.min_interval = min_interval
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self, sleep=time.sleep, now=time.monotonic) -> float:
        """Block until it is polite to send. Returns how long we waited."""
        with self._lock:
            gap = now() - self._last
            delay = max(0.0, self.min_interval - gap)
            if delay:
                sleep(delay)
            self._last = now() + delay
            return delay


@dataclass
class Cache:
    """A content addressed store of Compiler Explorer responses."""

    root: Path = field(default_factory=lambda: DEFAULT_STORE)
    limiter: RateLimiter = field(default_factory=RateLimiter)
    hits: int = 0
    misses: int = 0

    def __post_init__(self) -> None:
        self.root = Path(self.root)

    def path_for(self, key: str) -> Path:
        # Two characters of the hash as a subdirectory, so no directory ends up with
        # thousands of entries in it.
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict | None:
        p = self.path_for(key)
        if not p.exists():
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(p.read_text(encoding="utf-8"))

    def put(self, key: str, response: dict) -> Path:
        p = self.path_for(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(response, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return p

    def fetch(self, key: str, send) -> dict:
        """Return the cached response, or call `send()` and cache what comes back.

        `send` is passed in rather than imported so that a test, a notebook and CI can each
        decide what a request means. CI passes something that raises.
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        self.limiter.wait()
        response = send()
        self.put(key, response)
        return response

    @property
    def size(self) -> int:
        return len(list(self.root.rglob("*.json"))) if self.root.exists() else 0


class OfflineError(RuntimeError):
    """Raised when something wants the network and the network is not allowed."""


def refuse(*_args, **_kwargs):
    """A `send` that never sends. This is what CI uses."""
    raise OfflineError(
        "the Compiler Explorer cache missed and CI is not allowed to hit the live API. "
        "Run `just ce-refresh` locally and commit the new cache entries."
    )
