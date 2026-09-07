from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

ENV_PATH = BASE_DIR / ".env"
CONFIG_PATH = BASE_DIR / "config.json"

MANAGED_KEYS = [
    "DISCORD_TOKEN",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "FIREWORKS_API_KEY",
]

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": ["ai-chat", "music-play", "music-skip", "music-stop", "music-queue",
                "mod-kick", "mod-ban", "mod-purge", "fun-8ball", "util-poll",
                "game-trivia", "eco-daily", "eco-balance", "social-welcome"],
    "limits": {
        "cpu_percent": 75,
        "ram_mb": 700,
        "gpu_percent": 90,
        "max_concurrent": 4,
    },
    "ai": {
        "provider": "fireworks",
        "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "system_prompt": "You are a helpful, concise assistant inside a Discord server.",
    },
}


class ConfigStore:

    def __init__(self, env_path: Path = ENV_PATH) -> None:
        self.env_path = Path(env_path)
        if not self.env_path.exists():
            self.env_path.touch()
        load_dotenv(self.env_path, override=True)

    def get(self, key: str) -> Optional[str]:
        load_dotenv(self.env_path, override=True)
        return os.getenv(key)

    def set(self, key: str, value: str) -> None:
        if key not in MANAGED_KEYS:
            raise ValueError(f"Refusing to set unmanaged config key: {key}")
        value = value.strip()
        set_key(str(self.env_path), key, value)
        os.environ[key] = value

    def is_configured(self, key: str) -> bool:
        v = self.get(key)
        return bool(v and v.strip())

    @staticmethod
    def mask(value: Optional[str]) -> str:
        if not value or not value.strip():
            return "(not set)"
        v = value.strip()
        return "*" * len(v) if len(v) <= 6 else f"{v[:3]}...{v[-3:]}"


class RuntimeConfig:

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        if not self.path.exists():
            self._write(DEFAULT_CONFIG)
        self._data = self._read()

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return json.loads(json.dumps(DEFAULT_CONFIG))

    def _write(self, data: Dict[str, Any]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @property
    def enabled(self) -> List[str]:
        with self._lock:
            return list(self._data.get("enabled", []))

    @property
    def limits(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data.get("limits", DEFAULT_CONFIG["limits"]))

    @property
    def ai(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data.get("ai", DEFAULT_CONFIG["ai"]))

    def is_enabled(self, pipeline_id: str) -> bool:
        return pipeline_id in self.enabled

    def toggle(self, pipeline_id: str) -> bool:
        with self._lock:
            enabled = self._data.setdefault("enabled", [])
            if pipeline_id in enabled:
                enabled.remove(pipeline_id)
                on = False
            else:
                enabled.append(pipeline_id)
                on = True
            self._write(self._data)
            return on

    def set_enabled(self, ids: list[str]) -> None:
        with self._lock:
            self._data["enabled"] = list(dict.fromkeys(ids))
            self._write(self._data)

    def set_limits(self, cpu: int, ram_mb: int, gpu: int, max_concurrent: int) -> None:
        with self._lock:
            self._data["limits"] = {
                "cpu_percent": max(10, min(100, int(cpu))),
                "ram_mb": max(128, int(ram_mb)),
                "gpu_percent": max(10, min(100, int(gpu))),
                "max_concurrent": max(1, min(32, int(max_concurrent))),
            }
            self._write(self._data)

    def set_ai(self, provider: str, model: str, system_prompt: str) -> None:
        with self._lock:
            self._data["ai"] = {
                "provider": provider,
                "model": model.strip(),
                "system_prompt": system_prompt.strip() or DEFAULT_CONFIG["ai"]["system_prompt"],
            }
            self._write(self._data)


class JSONStore:

    def __init__(self, name: str) -> None:
        self.path = DATA_DIR / f"{name}.json"
        self._lock = threading.RLock()
        if not self.path.exists():
            self._write({})

    def _write(self, data: Any) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(self.path)

    def read(self) -> Any:
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}

    def write(self, data: Any) -> None:
        with self._lock:
            self._write(data)

    def update(self, fn) -> Any:
        with self._lock:
            data = self.read()
            data = fn(data) or data
            self._write(data)
            return data
