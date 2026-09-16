from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from .bot import BotController
from .catalog import Catalog
from .config import ConfigStore, MANAGED_KEYS, RuntimeConfig
from .discord_client import DiscordClient
from .engine import PipelineEngine
from .governor import Governor

_PAGE_PATH = Path(__file__).parent / "dashboard.html"

class SecretIn(BaseModel):
    key: str
    value: str
class LimitsIn(BaseModel):
    cpu_percent: int
    ram_mb: int
    gpu_percent: int
    max_concurrent: int
class AiIn(BaseModel):
    provider: str
    model: str
    system_prompt: str


def create_dashboard(
    config_store: ConfigStore,
    runtime: RuntimeConfig,
    catalog: Catalog,
    controller: BotController,
    discord_client: DiscordClient,
    governor: Governor,
    engine: PipelineEngine,
) -> FastAPI:
    app = FastAPI(title="business-BOT dashboard")

    def _status_payload() -> Dict[str, Any]:
        return {
            "bot_status": controller.status(),
            "desired": controller.desired,
            "last_error": controller.last_error,
            "token_configured": config_store.is_configured("DISCORD_TOKEN"),
            "governor": governor.snapshot(),
            "engine": engine.stats(),
        }

    @app.get("/api/status")
    async def get_status() -> JSONResponse:
        return JSONResponse(_status_payload())

    @app.post("/api/bot/start")
    async def bot_start() -> JSONResponse:
        msg = await controller.start()
        return JSONResponse({"message": msg, **_status_payload()})

    @app.post("/api/bot/stop")
    async def bot_stop() -> JSONResponse:
        msg = await controller.stop()
        return JSONResponse({"message": msg, **_status_payload()})

    @app.post("/api/bot/restart")
    async def bot_restart() -> JSONResponse:
        msg = await controller.restart()
        return JSONResponse({"message": msg, **_status_payload()})

    @app.get("/api/settings")
    async def get_settings() -> JSONResponse:
        return JSONResponse({
            k: config_store.mask(config_store.get(k)) for k in MANAGED_KEYS
        })

    @app.post("/api/settings")
    async def set_setting(body: SecretIn) -> JSONResponse:
        if body.key not in MANAGED_KEYS:
            raise HTTPException(status_code=400, detail=f"Unmanaged key: {body.key}")
        try:
            config_store.set(body.key, body.value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse({"message": f"{body.key} saved", **_status_payload()})

    @app.get("/api/catalog")
    async def get_catalog() -> JSONResponse:
        enabled = set(runtime.enabled)
        entries = [
            {**e, "enabled": e.get("id") in enabled}
            for e in catalog.all()
        ]
        return JSONResponse({"count": catalog.count(), "entries": entries})

    @app.post("/api/catalog/toggle/{pipeline_id}")
    async def toggle_catalog(pipeline_id: str) -> JSONResponse:
        if catalog.get(pipeline_id) is None:
            raise HTTPException(status_code=404, detail="Unknown catalog id")
        on = runtime.toggle(pipeline_id)
        discord_client.request_resync()
        return JSONResponse({"id": pipeline_id, "enabled": on})

    @app.get("/api/limits")
    async def get_limits() -> JSONResponse:
        return JSONResponse(runtime.limits)

    @app.post("/api/limits")
    async def set_limits(body: LimitsIn) -> JSONResponse:
        runtime.set_limits(body.cpu_percent, body.ram_mb, body.gpu_percent, body.max_concurrent)
        limits = runtime.limits
        governor.set_limits(limits["cpu_percent"], limits["ram_mb"], limits["gpu_percent"])
        engine.set_max_concurrent(limits["max_concurrent"])
        return JSONResponse(limits)

    @app.get("/api/ai")
    async def get_ai() -> JSONResponse:
        return JSONResponse(runtime.ai)

    @app.post("/api/ai")
    async def set_ai(body: AiIn) -> JSONResponse:
        runtime.set_ai(body.provider, body.model, body.system_prompt)
        return JSONResponse(runtime.ai)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _PAGE_PATH.read_text(encoding="utf-8")

    return app