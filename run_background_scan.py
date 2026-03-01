#!/usr/bin/env python3
from __future__ import annotations

import time
from datetime import datetime, timezone

import scan


# Edit these values directly in code.
SCAN_INTERVAL_SECONDS = 300  # 5 minutes
RETRY_DELAY_SECONDS = 30


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def main() -> int:
    print(f"[daemon] starting background scanner loop at {_utc_now()}")
    print(f"[daemon] interval: {SCAN_INTERVAL_SECONDS}s")

    run_count = 0
    while True:
        run_count += 1
        print(f"\n[daemon] run #{run_count} started at {_utc_now()}")

        try:
            exit_code = scan.main()
            print(f"[daemon] run #{run_count} finished with exit_code={exit_code} at {_utc_now()}")
            time.sleep(SCAN_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\n[daemon] stopped by user")
            return 0
        except Exception as exc:
            print(f"[daemon] run #{run_count} crashed: {exc}")
            print(f"[daemon] retrying in {RETRY_DELAY_SECONDS}s...")
            time.sleep(RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())