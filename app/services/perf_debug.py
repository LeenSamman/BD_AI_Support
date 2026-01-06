from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def elapsed_ms(start_ms: float) -> float:
    return now_ms() - start_ms


def log_perf(tag: str, extra: Optional[Dict[str, Any]] = None) -> None:
    logger = logging.getLogger("perf")
    payload = {"tag": tag, "t_ms": round(now_ms(), 2)}
    if extra:
        payload.update(extra)
    logger.info("PERF %s", payload)
