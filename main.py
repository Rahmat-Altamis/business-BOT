"""Process entrypoint — the only file that knows the *machine* exists.

main.py boots config/catalog, owns the resource governor and the pipeline
engine's concurrency limit (i.e. it knows how much CPU/RAM/GPU/parallelism
the process itself is allowed to use), starts/stops/supervises the Discord
client through BotController, and serves the web dashboard used to control
all of that.

main.py does NOT know what any command does. It never touches Discord
interactions, never imports business logic, and never looks inside a
handler's payload — it only starts, stops, restarts, and measures.

    main.py         -> lifecycle + performance (this file)
    discord_client.py -> pure forwarder: Discord in, pipeline call, render out
    pipelines/handlers.py -> every actual feature/pipeline lives here
"""
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
    # ---- config / catalog (data layer, no behaviour) ----
    config_store = ConfigStore()
    runtime = RuntimeConfig()
    catalog = Catalog()

    # ---- performance: main owns these two knobs ----
    limits = runtime.limits
    governor = Governor(
        cpu_percent=limits["cpu_percent"],
        ram_mb=limits["ram_mb"],
        gpu_percent=limits["gpu_percent"],
    )
    engine = PipelineEngine(max_concurrent=limits["max_concurrent"], governor=governor)

    # ---- wire the two other files together; main never looks inside either ----
    stores = handlers.register_all(engine, config_store, runtime, catalog)
    pipeline_client = PipelineClient(engine)
    discord_client = DiscordClient(pipeline_client, config_store, runtime, catalog, stores)
    controller = BotController(discord_client, config_store)

    app = create_dashboard(config_store, runtime, catalog, controller, discord_client, governor, engine)
    server = uvicorn.Server(
        uvicorn.Config(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT, log_level="warning")
    )

    # Start the bot if a token is already configured; if not, the dashboard's
    # /bot/start route (or the supervisor, once a token is pasted in) starts it.
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
