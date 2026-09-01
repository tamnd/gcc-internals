"""The cache and rate limiter that sit in front of Compiler Explorer.

Compiler Explorer is a free service run by volunteers. These tests are the part of the
project that keeps a promise to them.
"""

from __future__ import annotations

from tools.cecache import Cache, RateLimiter, request_key


def test_the_key_covers_everything_that_changes_the_answer():
    base = request_key("cg162", "int f;", "-O2", {"intel": True})
    assert base == request_key("cg162", "int f;", "-O2", {"intel": True})
    assert base != request_key("cg161", "int f;", "-O2", {"intel": True})
    assert base != request_key("cg162", "int g;", "-O2", {"intel": True})
    assert base != request_key("cg162", "int f;", "-O1", {"intel": True})
    assert base != request_key("cg162", "int f;", "-O2", {"intel": False})


def test_the_key_is_short_and_filename_safe():
    key = request_key("cg162", "int f;", "-O2")
    assert len(key) == 32
    assert key.isalnum()


def test_a_hit_does_not_call_send(tmp_path):
    cache = Cache(root=tmp_path)
    cache.put("abcd1234", {"code": 0})

    def send():
        raise AssertionError("a cache hit must not send")

    assert cache.fetch("abcd1234", send) == {"code": 0}
    assert (cache.hits, cache.misses) == (1, 0)


def test_a_miss_sends_once_and_keeps_the_answer(tmp_path):
    cache = Cache(root=tmp_path)
    calls = []

    def send():
        calls.append(1)
        return {"code": 0, "asm": []}

    cache.fetch("key1", send)
    cache.fetch("key1", send)
    assert len(calls) == 1
    assert cache.size == 1


def test_entries_are_sharded_so_no_directory_gets_huge(tmp_path):
    cache = Cache(root=tmp_path)
    path = cache.put("ab" + "0" * 30, {})
    assert path.parent.name == "ab"


def test_the_cache_file_is_readable_in_a_diff(tmp_path):
    """Cache entries are committed, so a reviewer has to be able to read the diff."""
    cache = Cache(root=tmp_path)
    path = cache.put("key1", {"code": 0, "asm": [{"text": "ret"}]})
    text = path.read_text()
    assert text.endswith("\n")
    assert "\n" in text.strip(), "one line of JSON is not a reviewable diff"


def test_the_limiter_waits_when_requests_are_too_close():
    clock = [100.0]
    slept = []
    limiter = RateLimiter(min_interval=1.0)

    assert limiter.wait(sleep=slept.append, now=lambda: clock[0]) == 0.0
    delay = limiter.wait(sleep=slept.append, now=lambda: clock[0])
    assert delay == 1.0
    assert slept == [1.0]


def test_the_limiter_does_not_wait_when_it_does_not_need_to():
    clock = [0.0]
    limiter = RateLimiter(min_interval=1.0)
    limiter.wait(sleep=lambda d: None, now=lambda: clock[0])
    clock[0] = 50.0
    assert limiter.wait(sleep=lambda d: None, now=lambda: clock[0]) == 0.0
