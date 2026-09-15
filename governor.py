from __future__ import annotations
import asyncio
import logging
from typing import Optional
import psutil

logger = logging.getloger("governor")

try:
    import pynvml
    pynvml.nvmlinit()
    _GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
    _GPU_AVAILABLE = True
except Exception:
    pynvml = None
    _GPU_HANDLE = None
    _GPU_AVAILABLE = False

class Governor:
    def __init__(self, cpu_percent: float, ram_mb: float, gpu_percent: float) -> None:
        self.cpu_limit = cpu_percent
        self.ram_limit_mb = ram_mb
        self.gpu_limit = gpu_percent
        self._process = psutil.Process()
        psutil.cpu_percent(interval=None)
        self._process.cpu_percent(interval=None)
        self.throttled_count = 0

    def set_limits(self, cpu_percent: float, ram_mb: float, gpu_percent: float) -> None:
        self.cpu_limit = cpu_percent
        self.ram_limit_mb = ram_mb
        self.gpu_limit = gpu_percent

    def _gpu_percent(self) -> Optional[float]:
        if not _GPU_AVAILABLE:
            return None
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(_GPU_HANDLE)
            return float(util.gpu)
        except Exception:
            return None

    def snapshot(self) -> dict:
        try:
            cpu = psutil.cpu_percent(interval=None)
        except Exception:
            cpu = 0.0
        try:
            ram_mb = self._process.memory_info().rss / (1024 * 1024)
        except Exception:
            ram_mb = 0.0
        gpu = self._gpu_percent()
        return {
            "cpu_percent": round(cpu, 1),
            "ram_mb": round(ram_mb, 1),
            "gpu_percent": round(gpu, 1) if gpu is not None else None,
            "gpu_available": _GPU_AVAILABLE,
            "limits": {
                "cpu_percent": self.cpu_limit,
                "ram_mb": self.ram_limit_mb,
                "gpu_percent": self.gpu_limit,
            },
            "throttled_count": self.throttled_count,
        }

def within_limits(self) -> bool:
        snap = self.snapshot()
        if snap["cpu_percent"] > self.cpu_limit:
            return False
        if snap["ram_mb"] > self.ram_limit_mb:
            return False
        if snap["gpu_percent"] is not None and snap["gpu_percent"] > self.gpu_limit:
            return False
        return True

async def wait_until_clear(self, timeout: float = 8.0, poll_seconds: float = 0.25) -> bool:
        if self.within_limits():
            return True
        self.throttled_count += 1
        logger.warning("Governor throttling: over configured resource limits")
        waited = 0.0
        while waited < timeout:
            await asyncio.sleep(poll_seconds)
            waited += poll_seconds
            if self.within_limits():
                return True
        logger.warning("Governor: still over limits after %.1fs, letting run through", timeout)
        return False

