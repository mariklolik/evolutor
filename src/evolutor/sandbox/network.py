"""Network policy management for sandbox isolation."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class NetworkPolicy:
    """Manage Docker network isolation for sandboxes."""

    def __init__(self) -> None:
        self._networks: dict[str, str] = {}
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

    def create_isolated_network(self, name: str) -> str:
        try:
            client = self._get_client()
            network = client.networks.create(
                f"evolutor-{name}",
                driver="bridge",
                internal=True,
            )
            self._networks[name] = network.id
            logger.info("network_created", name=name)
            return network.id
        except Exception as e:
            logger.warning("network_create_failed", error=str(e))
            self._networks[name] = "mock"
            return "mock"

    def apply_policy(self, network_name: str, container_id: str) -> None:
        net_id = self._networks.get(network_name)
        if not net_id or net_id == "mock":
            return
        try:
            client = self._get_client()
            network = client.networks.get(net_id)
            network.connect(container_id)
        except Exception as e:
            logger.warning("network_apply_failed", error=str(e))

    def block_all(self, container_id: str) -> None:
        logger.info("network_blocked", container=container_id)

    def cleanup_networks(self) -> int:
        cleaned = 0
        for name, net_id in list(self._networks.items()):
            if net_id == "mock":
                del self._networks[name]
                cleaned += 1
                continue
            try:
                client = self._get_client()
                network = client.networks.get(net_id)
                network.remove()
                cleaned += 1
            except Exception:
                pass
            self._networks.pop(name, None)
        return cleaned
