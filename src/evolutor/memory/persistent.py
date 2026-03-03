"""Persistent memory using Mem0."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class PersistentMemory:
    """Long-term memory using Mem0 (local or API mode)."""

    def __init__(self, api_key: str = "", use_local: bool = True) -> None:
        self.api_key = api_key
        self.use_local = use_local
        self._client = None
        self._local_store: list[dict] = []

    def _get_client(self):
        if self._client is not None:
            return self._client
        if self.use_local:
            return None
        try:
            from mem0 import MemoryClient
            self._client = MemoryClient(api_key=self.api_key)
            return self._client
        except Exception as e:
            logger.warning("mem0_init_failed", error=str(e))
            return None

    def store(self, content: str, metadata: dict | None = None, user_id: str = "evolutor") -> str:
        if self.use_local:
            entry = {"content": content, "metadata": metadata or {}, "user_id": user_id}
            self._local_store.append(entry)
            return f"local-{len(self._local_store) - 1}"
        client = self._get_client()
        if client:
            try:
                result = client.add(content, user_id=user_id, metadata=metadata)
                return str(result)
            except Exception as e:
                logger.warning("mem0_store_failed", error=str(e))
        return ""

    def search(self, query: str, user_id: str = "evolutor", top_k: int = 5) -> list[dict]:
        if self.use_local:
            query_lower = query.lower()
            results = []
            for entry in self._local_store:
                if query_lower in entry["content"].lower():
                    results.append(entry)
                if len(results) >= top_k:
                    break
            return results
        client = self._get_client()
        if client:
            try:
                return client.search(query, user_id=user_id, limit=top_k)
            except Exception as e:
                logger.warning("mem0_search_failed", error=str(e))
        return []

    def get_relevant_context(self, query: str, user_id: str = "evolutor") -> str:
        results = self.search(query, user_id=user_id)
        return "\n".join(r.get("content", str(r)) for r in results)

    def forget(self, memory_id: str) -> bool:
        if self.use_local:
            try:
                idx = int(memory_id.replace("local-", ""))
                if 0 <= idx < len(self._local_store):
                    self._local_store.pop(idx)
                    return True
            except ValueError:
                pass
            return False
        client = self._get_client()
        if client:
            try:
                client.delete(memory_id)
                return True
            except Exception:
                pass
        return False
