"""Resource limiting for sandbox containers."""

from __future__ import annotations

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class ResourceUsage(BaseModel):
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    pids: int = 0
    disk_mb: float = 0.0


class ResourceLimiter:
    """Configure and check resource limits for sandboxes."""

    def __init__(
        self,
        max_memory_mb: int = 512,
        max_cpu_cores: int = 1,
        max_pids: int = 256,
        max_disk_mb: int = 1024,
    ) -> None:
        self.max_memory_mb = max_memory_mb
        self.max_cpu_cores = max_cpu_cores
        self.max_pids = max_pids
        self.max_disk_mb = max_disk_mb

    def get_container_config(self) -> dict:
        return {
            "mem_limit": f"{self.max_memory_mb}m",
            "cpu_period": 100000,
            "cpu_quota": 100000 * self.max_cpu_cores,
            "pids_limit": self.max_pids,
            "storage_opt": {"size": f"{self.max_disk_mb}M"},
        }

    def check_usage(self, usage: ResourceUsage) -> list[str]:
        violations = []
        if usage.memory_mb > self.max_memory_mb:
            violations.append(f"Memory {usage.memory_mb:.1f}MB exceeds limit {self.max_memory_mb}MB")
        if usage.pids > self.max_pids:
            violations.append(f"PIDs {usage.pids} exceeds limit {self.max_pids}")
        if usage.disk_mb > self.max_disk_mb:
            violations.append(f"Disk {usage.disk_mb:.1f}MB exceeds limit {self.max_disk_mb}MB")
        return violations
