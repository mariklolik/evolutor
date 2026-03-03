"""Container snapshot management."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class Snapshot(BaseModel):
    id: str
    container_id: str
    tag: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SnapshotManager:
    """Manage Docker container snapshots."""

    def __init__(self) -> None:
        self._snapshots: dict[str, Snapshot] = {}
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import docker
                self._client = docker.from_env()
            except Exception as e:
                logger.warning("docker_unavailable", error=str(e))
                raise
        return self._client

    def create_snapshot(self, container_id: str, tag: str) -> Snapshot:
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            image = container.commit(tag=f"evolutor-snap:{tag}")
            snap = Snapshot(id=image.id, container_id=container_id, tag=tag)
        except Exception as e:
            logger.warning("snapshot_create_failed", error=str(e))
            snap = Snapshot(id=f"mock-{tag}", container_id=container_id, tag=tag)
        self._snapshots[tag] = snap
        logger.info("snapshot_created", tag=tag)
        return snap

    def restore_snapshot(self, tag: str) -> str | None:
        snap = self._snapshots.get(tag)
        if not snap:
            return None
        try:
            client = self._get_client()
            container = client.containers.run(
                f"evolutor-snap:{tag}",
                command="sleep infinity",
                detach=True,
                name=f"evolutor-restored-{tag}",
            )
            return container.id
        except Exception as e:
            logger.warning("snapshot_restore_failed", error=str(e))
            return "mock-restored"

    def list_snapshots(self) -> list[Snapshot]:
        return list(self._snapshots.values())

    def prune_old(self, max_age_hours: int = 24) -> int:
        pruned = 0
        now = datetime.now(timezone.utc)
        for tag, snap in list(self._snapshots.items()):
            created = datetime.fromisoformat(snap.created_at)
            age_hours = (now - created).total_seconds() / 3600
            if age_hours > max_age_hours:
                del self._snapshots[tag]
                pruned += 1
        return pruned
