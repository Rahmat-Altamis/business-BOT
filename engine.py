from __future__ import annotations
import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional
from .governor import Governor

logger = logging.getLogger("engine")
Handler = Callable[[Dict[str, Any]], Awaitable[Any]]

class PipelineEngine:
    def __init__(self, max_concurrent: int, governor: Governor) -> None:
        self.governor = governor
        self._max_concurrent = max(1, int(max_concurrent))
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._handlers: Dict[str, Handler] = {}
        self.active = 0
        self.total_run = 0
        self.total_failed = 0
        self.last_run_at: Optional[float] = None

    def register(self, pipeline_type: str, handler: Handler) -> None:
        if pipeline_type in self._handlers:
            logger.warning("overwriting existing hancler for pipeline type '%s'", pipeline_type)
            self._handlers[pipeline_type] = handler

    def set_max_concurrent(self, max_concurrent: int) -> None:
        self._max_concurrent = max(1, int(max_concurrent))
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

    @property
    def registered_types(self) -> list[str]:
        return list(self._handlers.keys())

    def stats(self) -> Dict[str, Any]:
        return {
            "active": self.active,
            "max_concurrent": self._max_concurrent,
            "total_run": self.total_run,
            "total_failed": self.total_failed,
            "last_run_at": self.last_run_at,
            "registered_types": self.registered_types(),
        }

    async def run(self, pipeline_type: str, payload: Dict[str, Any]) -> Any:
        handler = self._handlers.get(pipeline_type)
        if handler is None:
            raise ValueError(f"No handler registered for piepeline type '{pipeline_type}.")

        await self.governor.wait_until_clear()
        async with self._semaphore:
            self.active += 1
            self.last_run_at =  time.time()
            try:
                return await handler(payload)
            except Exception:
                self.total_failed += 1
                raise
            finally:
                self.total_run += 1
                self.active -= 1

class PipelineClient:
    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine

    async def run(self, pipeline_type: str, payload: Dict[str, Any]) -> Any:
        return await self.engine.run(pipeline_type, payload)

    def stats(self) -> Dict[str, Any]:
        return self.engine.stats()