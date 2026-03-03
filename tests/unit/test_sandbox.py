"""Unit tests for sandbox modules (mocked Docker)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from evolutor.sandbox.docker import SandboxManager, SandboxInstance, ExecutionResult
from evolutor.sandbox.resource import ResourceLimiter, ResourceUsage
from evolutor.sandbox.snapshot import SnapshotManager, Snapshot


class TestSandboxManager:
    def test_create_sandbox_mock(self):
        sm = SandboxManager()
        instance = asyncio.get_event_loop().run_until_complete(sm.create("test"))
        assert instance.id == "test"
        # Without Docker it falls back to mock
        assert instance.status in ("running", "mock")

    def test_execute_mock(self):
        sm = SandboxManager()
        instance = asyncio.get_event_loop().run_until_complete(sm.create("exec-test"))
        result = asyncio.get_event_loop().run_until_complete(sm.execute("exec-test", "echo hello"))
        assert isinstance(result, ExecutionResult)
        assert result.exit_code == 0

    def test_execute_not_found(self):
        sm = SandboxManager()
        result = asyncio.get_event_loop().run_until_complete(sm.execute("nonexistent", "echo"))
        assert result.exit_code == 1

    def test_list_active(self):
        sm = SandboxManager()
        asyncio.get_event_loop().run_until_complete(sm.create("a"))
        asyncio.get_event_loop().run_until_complete(sm.create("b"))
        active = asyncio.get_event_loop().run_until_complete(sm.list_active())
        assert len(active) == 2

    def test_destroy(self):
        sm = SandboxManager()
        asyncio.get_event_loop().run_until_complete(sm.create("to-destroy"))
        asyncio.get_event_loop().run_until_complete(sm.destroy("to-destroy"))
        active = asyncio.get_event_loop().run_until_complete(sm.list_active())
        assert len(active) == 0

    def test_cleanup_all(self):
        sm = SandboxManager()
        asyncio.get_event_loop().run_until_complete(sm.create("c1"))
        asyncio.get_event_loop().run_until_complete(sm.create("c2"))
        count = asyncio.get_event_loop().run_until_complete(sm.cleanup_all())
        assert count == 2


class TestResourceLimiter:
    def test_get_container_config(self):
        rl = ResourceLimiter(max_memory_mb=256, max_cpu_cores=2)
        config = rl.get_container_config()
        assert config["mem_limit"] == "256m"
        assert config["cpu_quota"] == 200000

    def test_check_usage_ok(self):
        rl = ResourceLimiter()
        usage = ResourceUsage(memory_mb=100, pids=50, disk_mb=200)
        violations = rl.check_usage(usage)
        assert len(violations) == 0

    def test_check_usage_violations(self):
        rl = ResourceLimiter(max_memory_mb=100, max_pids=10)
        usage = ResourceUsage(memory_mb=200, pids=20)
        violations = rl.check_usage(usage)
        assert len(violations) == 2


class TestSnapshotManager:
    def test_create_snapshot_mock(self):
        sm = SnapshotManager()
        snap = sm.create_snapshot("fake-container", "v1")
        assert snap.tag == "v1"
        assert snap.id.startswith("mock-")

    def test_list_snapshots(self):
        sm = SnapshotManager()
        sm.create_snapshot("c1", "snap1")
        sm.create_snapshot("c2", "snap2")
        snaps = sm.list_snapshots()
        assert len(snaps) == 2

    def test_restore_nonexistent(self):
        sm = SnapshotManager()
        result = sm.restore_snapshot("nonexistent")
        assert result is None
