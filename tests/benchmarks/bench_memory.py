"""Benchmarks for memory subsystem."""

from __future__ import annotations

from evolutor.memory.scratchpad import Scratchpad
from evolutor.memory.persistent import PersistentMemory


def test_scratchpad_set(benchmark):
    sp = Scratchpad()
    i = [0]

    def do_set():
        sp.set(f"key-{i[0]}", f"value-{i[0]}")
        i[0] += 1

    benchmark(do_set)


def test_scratchpad_get(benchmark):
    sp = Scratchpad()
    for j in range(100):
        sp.set(f"key-{j}", f"value-{j}")
    benchmark(sp.get, "key-50")


def test_persistent_memory_store(benchmark):
    pm = PersistentMemory(use_local=True)
    i = [0]

    def do_store():
        pm.store(f"Memory entry {i[0]}")
        i[0] += 1

    benchmark(do_store)


def test_persistent_memory_search(benchmark):
    pm = PersistentMemory(use_local=True)
    for j in range(50):
        pm.store(f"Pattern {j}: use try/except for error handling")
    benchmark(pm.search, "error handling")
