from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from app.services.doc_extractor import extract_rfp
from app.services.mem_debug import mem_mb


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()

    start_time = datetime.now().isoformat(timespec="seconds")
    start_rss = mem_mb()
    times_ms = []
    rss_samples = [start_rss]
    max_rss = start_rss

    for i in range(1, args.n + 1):
        t0 = time.perf_counter()
        extract_rfp(args.file)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        rss = mem_mb()
        times_ms.append(elapsed_ms)
        rss_samples.append(rss)
        max_rss = max(max_rss, rss)
        print(f"iter={i} elapsed_ms={elapsed_ms:.2f} rss_mb={rss:.2f}")

    end_rss = mem_mb()
    delta_rss = end_rss - start_rss
    avg_ms = statistics.mean(times_ms) if times_ms else 0.0
    max_ms = max(times_ms) if times_ms else 0.0

    print("summary:")
    print(f"start_time={start_time}")
    print(f"start_rss_mb={start_rss:.2f}")
    print(f"max_rss_mb={max_rss:.2f}")
    print(f"end_rss_mb={end_rss:.2f}")
    print(f"delta_rss_mb={delta_rss:.2f}")
    print(f"avg_time_ms={avg_ms:.2f}")
    print(f"max_time_ms={max_ms:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
