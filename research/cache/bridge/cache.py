# Semantic Cache — rule+priority 시그니처 기반 LLM 응답 재사용

import hashlib
import time


class SemanticCache:
    """
    동일한 rule + priority 조합이면 TTL 내 LLM 응답 재사용.
    캐시 키: MD5(rule:priority)
    """

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._store: dict[str, dict] = {}
        self.ttl    = ttl_seconds
        self.hits   = 0
        self.misses = 0

    def _key(self, payload: dict) -> str:
        sig = f"{payload.get('rule', '')}:{payload.get('priority', '')}"
        return hashlib.md5(sig.encode()).hexdigest()

    def get(self, payload: dict) -> dict | None:
        key = self._key(payload)
        entry = self._store.get(key)
        if entry and (time.time() - entry["ts"]) < self.ttl:
            self.hits += 1
            return {"result": entry["result"], "cache_key": key}
        self.misses += 1
        return None

    def set(self, payload: dict, result: dict) -> str:
        key = self._key(payload)
        self._store[key] = {"result": result, "ts": time.time()}
        return key

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
