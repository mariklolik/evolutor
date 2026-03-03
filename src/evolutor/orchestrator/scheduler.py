"""Task scheduler using Redis Streams with asyncio.Queue fallback."""

from __future__ import annotations

import asyncio
import json

import structlog

logger = structlog.get_logger()


class TaskScheduler:
    """Task queue using Redis Streams, falling back to asyncio.Queue."""

    def __init__(self, redis_url: str = "redis://localhost:6379", stream_name: str = "evolutor:tasks") -> None:
        self.redis_url = redis_url
        self.stream_name = stream_name
        self._redis = None
        self._fallback_queue: asyncio.Queue | None = None

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self.redis_url)
            await self._redis.ping()
            return self._redis
        except Exception as e:
            logger.warning("redis_unavailable", error=str(e))
            self._fallback_queue = asyncio.Queue()
            return None

    async def enqueue(self, task_data: dict) -> str:
        try:
            r = await self._get_redis()
            if r:
                msg_id = await r.xadd(self.stream_name, {"data": json.dumps(task_data)})
                return msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
            if self._fallback_queue is not None:
                await self._fallback_queue.put(task_data)
                return f"local-{self._fallback_queue.qsize()}"
        except Exception as e:
            logger.error("enqueue_error", error=str(e), exc_info=True)
        return ""

    async def dequeue(self, consumer_group: str = "workers", consumer_name: str = "w1") -> dict | None:
        r = await self._get_redis()
        if r:
            try:
                # Create consumer group if needed
                try:
                    await r.xgroup_create(self.stream_name, consumer_group, id="0", mkstream=True)
                except Exception:
                    pass
                messages = await r.xreadgroup(consumer_group, consumer_name, {self.stream_name: ">"}, count=1, block=5000)
                if messages:
                    for stream, msgs in messages:
                        for msg_id, data in msgs:
                            return {"id": msg_id, "data": json.loads(data[b"data"])}
            except Exception as e:
                logger.warning("redis_dequeue_failed", error=str(e))
        if self._fallback_queue is not None:
            try:
                return await asyncio.wait_for(self._fallback_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                return None
        return None

    async def acknowledge(self, msg_id: str, consumer_group: str = "workers") -> None:
        try:
            r = await self._get_redis()
            if r:
                await r.xack(self.stream_name, consumer_group, msg_id)
        except Exception as e:
            logger.error("acknowledge_error", msg_id=msg_id, error=str(e), exc_info=True)
