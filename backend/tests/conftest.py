from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeRedis:
    """The handful of set/TTL commands the coverage helpers use."""

    def __init__(self):
        self.sets: dict[str, set[str]] = {}
        self.ttls: dict[str, int] = {}
        self.values: dict[str, bytes] = {}

    def sadd(self, key, *members):
        self.sets.setdefault(key, set()).update(members)

    def srem(self, key, *members):
        self.sets.get(key, set()).difference_update(members)

    def smembers(self, key):
        return {m.encode() for m in self.sets.get(key, set())}

    def expire(self, key, seconds):
        self.ttls[key] = seconds

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.values[key] = value.encode() if isinstance(value, str) else value
        if ex:
            self.ttls[key] = ex

    def exists(self, key):
        return int(key in self.values or key in self.hashes)

    def delete(self, key):
        existed = key in self.values
        self.values.pop(key, None)
        return int(existed)

    def ttl(self, key):
        return self.ttls.get(key, -2) if key in self.values else -2

    # hashes
    @property
    def hashes(self) -> dict:
        if not hasattr(self, "_hashes"):
            self._hashes = {}
        return self._hashes

    def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update({k: str(v) for k, v in mapping.items()})

    def hget(self, key, field):
        val = self.hashes.get(key, {}).get(field)
        return val.encode() if val is not None else None

    def hgetall(self, key):
        return {k.encode(): v.encode() for k, v in self.hashes.get(key, {}).items()}

    def hincrby(self, key, field, amount):
        h = self.hashes.setdefault(key, {})
        h[field] = str(int(h.get(field, "0")) + amount)


@pytest.fixture
def fake_redis():
    return FakeRedis()
