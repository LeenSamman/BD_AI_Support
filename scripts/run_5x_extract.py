from __future__ import annotations

import argparse
import os
import time

import requests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000/rfp/upload")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()

    if args.health:
        try:
            health_resp = requests.get("http://127.0.0.1:8000/")
        except requests.exceptions.ConnectionError:
            print('Server unreachable. Start uvicorn first: uvicorn app.main:app --host 127.0.0.1 --port 8000')
            return 1
        if health_resp.status_code != 200:
            print(f"Health check failed: GET / returned {health_resp.status_code}")
            return 1

    rows = []
    for i in range(1, args.n + 1):
        try:
            with open(args.file, "rb") as f:
                files = {"file": (os.path.basename(args.file), f, "application/pdf")}
                start = time.perf_counter()
                resp = requests.post(args.url, files=files)
                elapsed = time.perf_counter() - start
        except requests.exceptions.ConnectionError:
            print('Server unreachable. Start uvicorn first: uvicorn app.main:app --host 127.0.0.1 --port 8000')
            return 1

        status = "ok" if resp.status_code == 200 else f"err:{resp.status_code}"
        rss_before = resp.headers.get("X-Server-RSS-Before", "")
        rss_after_worker = resp.headers.get("X-Server-RSS-After-Worker", "")
        rss_after_read = resp.headers.get("X-Server-RSS-After-Read", "")
        rows.append(
            (
                i,
                status,
                rss_before,
                rss_after_worker,
                rss_after_read,
                f"{elapsed:.2f}",
            )
        )

    header = (
        "run_idx",
        "status",
        "server_rss_before",
        "server_rss_after_worker",
        "server_rss_after_read",
        "elapsed_sec",
    )
    widths = [len(h) for h in header]
    for row in rows:
        for idx, val in enumerate(row):
            widths[idx] = max(widths[idx], len(str(val)))

    def fmt_row(row):
        return " | ".join(str(val).ljust(widths[idx]) for idx, val in enumerate(row))

    print(fmt_row(header))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt_row(row))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
