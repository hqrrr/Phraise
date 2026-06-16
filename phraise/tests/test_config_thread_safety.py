# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for config thread safety.
"""Thread-safety tests for Config singleton.

Verifies that:
- Singleton creation is race-free (double-checked locking).
- Concurrent set() calls do not lose or interleave data.
- Concurrent update_section() calls are safe.
"""

import random
import string
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from phraise.config import Config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton between tests so each test starts fresh."""
    Config._instance = None
    yield
    Config._instance = None


# ---------------------------------------------------------------------------
# Singleton thread-safety (double-checked locking)
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance_from_multiple_threads():
    """Multiple threads racing on Config() must all get the same instance."""

    results: list[int] = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(10)  # synchronise the race start

    def _create():
        barrier.wait()  # all threads wait here, then race
        c = Config()
        with results_lock:
            results.append(id(c))

    threads = [threading.Thread(target=_create) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All ids should be identical
    first = results[0]
    assert all(r == first for r in results), (
        f"Got {len(set(results))} different Config instances from 10 threads"
    )


def test_singleton_initialised_only_once():
    """Config.__init__ must only load/save data on the first construction."""
    Config._instance = None

    configs = [Config() for _ in range(5)]
    first_id = id(configs[0])
    assert all(id(c) == first_id for c in configs), "Not all Config() returned the same instance"


# ---------------------------------------------------------------------------
# Concurrent set() safety
# ---------------------------------------------------------------------------

def test_concurrent_set_preserves_all_keys():
    """50 threads writing to different keys must not lose any writes."""
    config = Config()
    num_threads = 50

    def _writer(idx: int):
        key = f"thread_key_{idx}"
        config.set("test_section", key, value=idx)

    threads = [threading.Thread(target=_writer, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify every value survived
    for i in range(num_threads):
        key = f"thread_key_{i}"
        val = config.get("test_section", key, default=None)
        assert val == i, (
            f"Missing or wrong value for {key}: expected {i}, got {val}"
        )


def test_concurrent_set_on_same_key_last_writer_wins():
    """10 threads writing to the same key — the final value must be one of the writes (no corruption)."""
    config = Config()

    def _writer(val: int):
        config.set("same_section", "same_key", value=val)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_writer, i) for i in range(10)]
        for f in as_completed(futures):
            f.result()  # re-raise if any failed

    val = config.get("same_section", "same_key")
    assert val is not None, "Key was lost entirely"
    assert isinstance(val, int), f"Value corrupted: expected int, got {type(val).__name__}"
    # The last write wins — any value 0-9 is valid, as long as the data structure is intact
    assert 0 <= val <= 9, f"Value {val} is outside expected range"


def test_concurrent_set_deeply_nested_keys():
    """Deeply nested key writes from multiple threads must not interleave."""
    config = Config()
    num_threads = 30

    def _writer(idx: int):
        # Each thread writes to a unique deep path
        config.set("a", "b", "c", f"leaf_{idx}", value=idx)

    threads = [threading.Thread(target=_writer, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i in range(num_threads):
        val = config.get("a", "b", "c", f"leaf_{i}")
        assert val == i, (
            f"Nested key leaf_{i}: expected {i}, got {val}"
        )


# ---------------------------------------------------------------------------
# Concurrent update_section() safety
# ---------------------------------------------------------------------------

def test_concurrent_update_section():
    """Multiple threads updating different sections must not interfere."""
    config = Config()

    # Pre-seed sections so update_section's "if section in self._data" passes
    for sec in ["sect_a", "sect_b", "sect_c", "sect_d", "sect_e"]:
        config.set(sec, "initial", value="seed")

    def _writer(section: str, key: str, val: int):
        config.update_section(section, {key: val, "initial": "done"})

    sections = ["sect_a", "sect_b", "sect_c", "sect_d", "sect_e"]
    threads = []
    for i, sec in enumerate(sections):
        t = threading.Thread(target=_writer, args=(sec, f"k_{i}", i))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i, sec in enumerate(sections):
        val = config.get(sec, f"k_{i}")
        assert val == i, (
            f"Section {sec} key k_{i}: expected {i}, got {val}"
        )
        assert config.get(sec, "initial") == "done", (
            f"Section {sec}: 'initial' key should have been updated to 'done'"
        )


# ---------------------------------------------------------------------------
# Stress: mixed reads and writes
# ---------------------------------------------------------------------------

def test_mixed_read_write_stress():
    """Concurrent readers and writers must not deadlock or corrupt."""
    config = Config()
    stop = threading.Event()

    def _writer():
        idx = 0
        while not stop.is_set():
            config.set("stress", f"key_{idx % 20}", value=idx)
            idx += 1

    def _reader():
        while not stop.is_set():
            _ = config.get("stress", "key_0", default=None)

    writers = [threading.Thread(target=_writer) for _ in range(5)]
    readers = [threading.Thread(target=_reader) for _ in range(5)]

    for t in writers + readers:
        t.start()

    # Let them hammer for 0.5 seconds
    threading.Event().wait(0.5)
    stop.set()

    for t in writers + readers:
        t.join(timeout=5)
        assert not t.is_alive(), "Thread failed to join — possible deadlock"
