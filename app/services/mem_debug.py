from __future__ import annotations

import logging
import os

import psutil


def mem_mb() -> float:
    process = psutil.Process(os.getpid())
    rss = process.memory_info().rss
    return rss / (1024 * 1024)


def log_mem(tag: str) -> None:
    logger = logging.getLogger("mem")
    logger.info("MEM tag=%s rss_mb=%.2f", tag, mem_mb())
