from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from app.services.doc_extractor import extract_rfp
from app.services.mem_debug import log_mem


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    log_mem("worker:start")
    log_mem("worker:before_extract")
    result = extract_rfp(args.file)
    log_mem("worker:after_extract")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
