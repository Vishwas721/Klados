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


@pytest.fixture
def fake_redis():
    return FakeRedis()
