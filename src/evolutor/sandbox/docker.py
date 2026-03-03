"""Docker-based sandbox management."""

from __future__ import annotations

import asyncio
import uuid

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ExecutionResult(BaseModel):
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False


class SandboxInstance(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    container_id: str = ""
    image: str = "python:3.11-slim"
    status: str = "created"
    workdir: str = "/workspace"


class SandboxManager:
    """Manage Docker sandbox containers for safe code execution."""

    def __init__(self, image: str = "python:3.11-slim", timeout: int = 300) -> None:
        self.image = image
        self.timeout = timeout
        self._instances: dict[str, SandboxInstance] = {}
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

    async def create(self, name: str | None = None) -> SandboxInstance:
        instance = SandboxInstance(image=self.image)
        if name:
            instance.id = name
        try:
            client = self._get_client()
            container = client.containers.create(
                self.image,
                command="sleep infinity",
                detach=True,
                working_dir="/workspace",
                mem_limit="512m",
                pids_limit=256,
                network_mode="none",
                name=f"evolutor-{instance.id}",
            )
            instance.container_id = container.id
            container.start()
            instance.status = "running"
        except Exception as e:
            logger.warning("sandbox_create_failed", error=str(e))
            instance.status = "mock"
        self._instances[instance.id] = instance
        logger.info("sandbox_created", id=instance.id, status=instance.status)
        return instance

    async def execute(self, instance_id: str, command: str, timeout: int | None = None) -> ExecutionResult:
        instance = self._instances.get(instance_id)
        if not instance:
            return ExecutionResult(exit_code=1, stderr=f"Instance {instance_id} not found")
        if instance.status == "mock":
            return ExecutionResult(exit_code=0, stdout="(mock execution)", stderr="")
        try:
            client = self._get_client()
            container = client.containers.get(instance.container_id)
            exec_timeout = timeout or self.timeout
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: container.exec_run(
                    ["sh", "-c", command],
                    workdir="/workspace",
                ),
            )
            return ExecutionResult(
                exit_code=result.exit_code,
                stdout=result.output.decode("utf-8", errors="replace") if result.output else "",
            )
        except Exception as e:
            return ExecutionResult(exit_code=1, stderr=str(e))

    async def destroy(self, instance_id: str) -> None:
        instance = self._instances.pop(instance_id, None)
        if not instance:
            return
        if instance.status != "mock" and instance.container_id:
            try:
                client = self._get_client()
                container = client.containers.get(instance.container_id)
                container.stop(timeout=5)
                container.remove(force=True)
            except Exception as e:
                logger.warning("sandbox_destroy_failed", error=str(e))
        logger.info("sandbox_destroyed", id=instance_id)

    async def list_active(self) -> list[SandboxInstance]:
        return list(self._instances.values())

    async def cleanup_all(self) -> int:
        ids = list(self._instances.keys())
        for instance_id in ids:
            await self.destroy(instance_id)
        return len(ids)
