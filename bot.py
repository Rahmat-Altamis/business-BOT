from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional
logger = logging.getLogger("bot.controller")


class BotController:

    def __init__(self, discord_client, config_store) -> None:
        self.client = discord_client
        self.config = config_store
        self.task: Optional[asyncio.Task] = None
        self.desired = "stopped"  # "running" | "stopped"
        self.last_error: Optional[str] = None
        self._failed = False
        self._failed_at = 0.0

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def status(self) -> str:
        if self.running:
            return self.client.status
        return "OFFLINE"

    async def start(self) -> str:
        if self.running:
            return "already running"
        if not self.config.is_configured("DISCORD_TOKEN"):
            self.desired = "running"
            return "token missing — paste the Discord token in Settings"
        self.desired = "running"
        self._failed = False
        self.last_error = None
        self.task = asyncio.create_task(self._run())
        return "starting"

    async def stop(self) -> str:
        self.desired = "stopped"
        if self.running and self.task is not None:
            try:
                await self.client.close()
                await asyncio.wait_for(self.task, timeout=15)
            except asyncio.TimeoutError:
                self.task.cancel()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Stop failed")
        self.task = None
        return "stopped"

    async def restart(self) -> str:
        await self.stop()
        return await self.start()

    async def _run(self) -> None:
        try:
            await self.client.start()
            self._failed = False
        except Exception as exc:
            self._failed = True
            self._failed_at = time.time()
            self.last_error = str(exc)[:200]
            logger.exception("Discord client crashed")
        finally:
            self.client.status = "OFFLINE"

    async def supervisor(self, poll_seconds: float = 3.0, fail_backoff: float = 30.0) -> None:
        while True:
            try:
                if (
                    self.desired == "running"
                    and not self.running
                    and self.config.is_configured("DISCORD_TOKEN")
                    and (not self._failed or time.time() - self._failed_at > fail_backoff)
                ):
                    logger.info("Supervisor: starting Discord client")
                    self._failed = False
                    self.task = asyncio.create_task(self._run())
            except Exception:
                logger.exception("Supervisor error")
            await asyncio.sleep(poll_seconds)
