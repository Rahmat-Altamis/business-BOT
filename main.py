from __future__ import annotations
import asyncio
import logging
import uvicorn
from .bot import BotController
from .catalog import Catalog
from .config import ConfigStore, RuntimeConfig
from .dashboard import create_dashboard
from .discord_client import DiscordClient
from .engine import PipelineClient, PipelineEngine
from .governor import Governor
from .pipelines import handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("main")

DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8080


async def run() -> None:
    config_store = ConfigStore()
    runtime = RuntimeConfig()
    catalog = Catalog()
    limits = runtime.limits
    governor = Governor(
        cpu_percent=limits["cpu_percent"],
        ram_mb=limits["ram_mb"],
        gpu_percent=limits["gpu_percent"],
    )
    engine = PipelineEngine(max_concurrent=limits["max_concurrent"], governor=governor)
    stores = handlers.register_all(engine, config_store, runtime, catalog)
    pipeline_client = PipelineClient(engine)
    discord_client = DiscordClient(pipeline_client, config_store, runtime, catalog, stores)
    controller = BotController(discord_client, config_store)

    app = create_dashboard(config_store, runtime, catalog, controller, discord_client, governor, engine)
    server = uvicorn.Server(
        uvicorn.Config(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT, log_level="warning")
    )

    await controller.start()
    logger.info("Dashboard on http://%s:%d", DASHBOARD_HOST, DASHBOARD_PORT)
    try:
        await asyncio.gather(
            server.serve(),
            controller.supervisor(),
            discord_client.reminder_loop(),
        )
    finally:
        await controller.stop()

def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Shutting down")


if __name__ == "__main__":
    main()