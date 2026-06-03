import hashlib
import json
import os

import redis
from dotenv import load_dotenv

load_dotenv()


class SemanticCache:
    def __init__(self):
        self.ttl = int(os.getenv("CACHE_TTL", "3600"))
        self.client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379"),
            decode_responses=True,
        )
        self._hits = 0
        self._misses = 0

    def _key(self, rule: str, priority: str) -> str:
        source = f"{rule}:{priority}"
        return hashlib.md5(source.encode("utf-8")).hexdigest()

    def get(self, rule, priority) -> dict | None:
        cached = self.client.get(self._key(rule, priority))
        if not cached:
            self._misses += 1
            return None

        self._hits += 1
        return json.loads(cached)

    def set(self, rule, priority, result) -> str:
        key = self._key(rule, priority)
        self.client.setex(key, self.ttl, json.dumps(result, ensure_ascii=False))
        return key

    def delete(self, rule, priority):
        self.client.delete(self._key(rule, priority))

    @property
    def hit_rate(self):
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total


semantic_cache = SemanticCache()
