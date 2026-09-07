from __future__ import annotations

import asyncio
import logging
import socket
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import uvicorn

from app.bot import BotController
from app.catalog import Catalog
from app.config import ConfigStore, RuntimeConfig
from app.dashboard import create_dashboard
from app.discord_client import DiscordClient
from app.engine import PipelineClient, PipelineEngine
from app.governor import Governor
from app.pipelines.handlers import register_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8000


def find_free_port(host: str, preferred: int, tries: int = 5) -> int:
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free dashboard port found in {preferred}-{preferred + tries - 1}")


def ensure_catalog() -> Catalog:
    path = BASE_DIR / "catalog.json"
    if not path.exists():
        logger.info("catalog.json missing — generating (100+ pipelines)")
        subprocess.run(
            [sys.executable, str(BASE_DIR / "tools" / "gen_catalog.py")],
            check=True,
            cwd=str(BASE_DIR),
        )
    return Catalog(path)


async def run_all() -> None:
    config_store = ConfigStore()
    runtime = RuntimeConfig()
    catalog = ensure_catalog()

    limits = runtime.limits
    governor = Governor(
        cpu_percent=limits["cpu_percent"],
        ram_mb=limits["ram_mb"],
        gpu_percent=limits["gpu_percent"],
    )
    engine = PipelineEngine(max_concurrent=limits["max_concurrent"], governor=governor)
    stores = register_all(engine, config_store, runtime, catalog)
    pipeline_client = PipelineClient(engine)

    discord_client = DiscordClient(pipeline_client, config_store, runtime, catalog, stores)
    controller = BotController(discord_client, config_store)

    app = create_dashboard(
        config_store=config_store,
        runtime=runtime,
        catalog=catalog,
        controller=controller,
        discord_client=discord_client,
        governor=governor,
        engine=engine,
    )

    # Non-technical owner UX: if a token is already saved, just start.
    if config_store.is_configured("DISCORD_TOKEN"):
        controller.desired = "running"

    port = find_free_port(DASHBOARD_HOST, DASHBOARD_PORT)
    server = uvicorn.Server(
        uvicorn.Config(app, host=DASHBOARD_HOST, port=port, log_level="warning")
    )
    logger.info(
        "Dashboard -> http://%s:%d | %d pipelines in catalog, %d enabled",
        DASHBOARD_HOST, port, catalog.count(), len(runtime.enabled),
    )
    await asyncio.gather(
        server.serve(),
        controller.supervisor(),
        discord_client.reminder_loop(),
    )


def main() -> None:
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        logger.info("Shutting down (Ctrl+C).")


if __name__ == "__main__":
    main()
