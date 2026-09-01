from __future__ import annotations

import time
from collections import defaultdict, deque


class TieredMemory:
    """Hot/warm in-memory context with cached institutional retrieval."""

    def __init__(self, durable_store, hot_items=1000, warm_items=10000, cold_ttl_seconds=60):
        self.durable = durable_store
        self.hot = defaultdict(lambda: deque(maxlen=hot_items))
        self.warm = defaultdict(lambda: deque(maxlen=warm_items))
        self.cold_ttl_seconds = cold_ttl_seconds
        self._cold_cache = {}

    def observe(self, subject, event):
        self.hot[subject].append(event)
        self.warm[subject].append(event)

    def institutionalize(self, subject, summary, evidence=None, confidence=.5):
        self.durable.remember("institutional", subject, summary, evidence, confidence)
        self._cold_cache.pop(subject, None)

    def _cold(self, subject, n):
        now = time.time()
        cached = self._cold_cache.get(subject)
        if cached and now - cached[0] < self.cold_ttl_seconds:
            return cached[1][:n]
        rows = self.durable.recall(subject, max(n, 8))
        self._cold_cache[subject] = (now, rows)
        return rows[:n]

    def prefetch(self, subjects, n=8):
        rows = self.durable.recall_many(list(subjects), n) if hasattr(self.durable, "recall_many") else {s: self.durable.recall(s, n) for s in subjects}
        now = time.time()
        for subject, values in rows.items():
            self._cold_cache[subject] = (now, values)
        return rows

    def packet(self, subject, hot_n=10, warm_n=10, cold_n=6):
        return {
            "hot": list(self.hot[subject])[-hot_n:],
            "warm": list(self.warm[subject])[-warm_n:],
            "institutional": self._cold(subject, cold_n),
        }
