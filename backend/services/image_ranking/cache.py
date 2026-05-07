from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class SimpleTTLCache:
    def __init__(self, *, default_ttl_s: float = 3600.0, max_items: int = 10_000):
        self.default_ttl_s = float(default_ttl_s)
        self.max_items = int(max_items)
        self._store: Dict[str, CacheEntry] = {}

    def _now(self) -> float:
        return time.time()

    def get(self, key: str) -> Optional[Any]:
        ent = self._store.get(key)
        if not ent:
            return None
        if ent.expires_at < self._now():
            self._store.pop(key, None)
            return None
        return ent.value

    def set(self, key: str, value: Any, *, ttl_s: Optional[float] = None) -> None:
        if len(self._store) >= self.max_items:
            # simple eviction: drop oldest expires_at
            oldest_key = min(self._store.items(), key=lambda kv: kv[1].expires_at)[0]
            self._store.pop(oldest_key, None)
        ttl = self.default_ttl_s if ttl_s is None else float(ttl_s)
        self._store[key] = CacheEntry(value=value, expires_at=self._now() + ttl)

