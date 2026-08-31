"""
Document Fingerprint Cache

Ensures that analyzing the same document always produces the same result.
Uses a SHA-256 hash of the parsed text as the cache key.

Industry-grade consistency mechanism: once a document has been analyzed,
re-analysis returns the cached result instantly, eliminating LLM non-determinism
entirely for repeat runs.

Cache is in-memory by default. For production, swap in Redis or disk-based storage.
"""

import hashlib
import json
import os
import time
from typing import Optional


# ── Configuration ────────────────────────────────────────────────────────────

CACHE_DIR = os.path.join(os.path.dirname(__file__), "../.cache")
CACHE_TTL_SECONDS = 86400  # 24 hours — re-analyze after this


class DocumentCache:
    """
    Content-addressed cache for pipeline results.
    Key = SHA-256 of the parsed document text.
    Value = full pipeline output (findings, score, report, etc.)
    """

    def __init__(self, cache_dir: Optional[str] = None, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.cache_dir = cache_dir or CACHE_DIR
        self.ttl = ttl_seconds
        self._memory_cache: dict[str, dict] = {}  # in-process cache layer
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_cache_key(self, parsed_text: str) -> str:
        """Generate a deterministic cache key from document text."""
        normalized = parsed_text.strip().encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()

    def get(self, parsed_text: str) -> Optional[dict]:
        """
        Look up cached results for this document.
        Returns None if no cache hit or cache expired.
        """
        key = self.get_cache_key(parsed_text)

        # Layer 1: in-memory (fastest)
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if time.time() - entry["timestamp"] < self.ttl:
                return entry["data"]
            else:
                del self._memory_cache[key]

        # Layer 2: disk-based
        cache_path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                if time.time() - entry["timestamp"] < self.ttl:
                    # Promote to memory cache
                    self._memory_cache[key] = entry
                    return entry["data"]
                else:
                    os.remove(cache_path)
            except (json.JSONDecodeError, KeyError):
                # Corrupted cache entry — delete it
                try:
                    os.remove(cache_path)
                except OSError:
                    pass

        return None

    def set(self, parsed_text: str, data: dict):
        """
        Store pipeline results for this document.
        Writes to both memory and disk for persistence.
        """
        key = self.get_cache_key(parsed_text)
        entry = {
            "timestamp": time.time(),
            "data": data,
        }

        # Layer 1: memory
        self._memory_cache[key] = entry

        # Layer 2: disk
        cache_path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, default=str)
        except OSError as e:
            print(f"[CACHE] Warning: could not write disk cache: {e}")

    def invalidate(self, parsed_text: str):
        """Remove cached results for a specific document."""
        key = self.get_cache_key(parsed_text)
        self._memory_cache.pop(key, None)
        cache_path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            if os.path.exists(cache_path):
                os.remove(cache_path)
        except OSError:
            pass

    def clear(self):
        """Clear the entire cache."""
        self._memory_cache.clear()
        if os.path.exists(self.cache_dir):
            for fname in os.listdir(self.cache_dir):
                if fname.endswith(".json"):
                    try:
                        os.remove(os.path.join(self.cache_dir, fname))
                    except OSError:
                        pass


# ── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    cache = DocumentCache()

    test_text = "This is a test contract with Section 1 and Section 2."
    test_data = {"score": 85, "findings": [{"category": "payment_terms"}]}

    # Should be empty initially
    result = cache.get(test_text)
    print(f"Cache miss: {result}")

    # Store
    cache.set(test_text, test_data)
    print("Stored in cache.")

    # Should hit
    result = cache.get(test_text)
    print(f"Cache hit: score={result['score']}, findings={len(result['findings'])}")

    # Different text should miss
    result2 = cache.get("Different contract text entirely.")
    print(f"Different text: {result2}")

    # Clear
    cache.clear()
    result3 = cache.get(test_text)
    print(f"After clear: {result3}")
    print("Cache test passed!")
