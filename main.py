
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


BUFFER_FILE = Path("chronosmatch_ring.dat")
STATS_FILE = Path("dashboard/live_stats.json")


def main():
    parser = argparse.ArgumentParser(
        description="ChronosMatch Trading Engine Launcher"
    )

    parser.add_argument(
        "--orders", type=int, default=20000
    )

    parser.add_argument(
        "--rate", type=int, default=5000
    )

    args = parser.parse_args()

    if args.orders <= 0 or args.rate <= 0:
        parser.error("--orders and --rate must be positive")

    print("=" * 60)
    print("           CHRONOSMATCH TRADING ENGINE")
    print("=" * 60)

    print(f"Orders : {args.orders:,}")
    print(f"Rate   : {args.rate:,} orders/sec")

    if BUFFER_FILE.exists():
        BUFFER_FILE.unlink()

    if STATS_FILE.exists():
        STATS_FILE.unlink()

    processes = []

    try:
        consumer = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "engine.consumer",
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        processes.append(consumer)

        print("Consumer launched.")

        # Allow the consumer to initialize.
        time.sleep(1)

        producer = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "simulator.market_firehose",
                "--orders",
                str(args.orders),
                "--rate",
                str(args.rate),
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        processes.append(producer)

        print("Producer launched.")

        time.sleep(1)

        dashboard = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "dashboard.run_dashboard",
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        processes.append(dashboard)

        print("Dashboard launched.")
        print()
        print("ChronosMatch is running.")
        print("Press Ctrl+C here to stop launched processes.")

        while True:
            if producer.poll() is not None:
                print("Producer finished.")
                break

            time.sleep(0.5)

        print("Waiting for dashboard. Press Ctrl+C to stop.")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping ChronosMatch...")

    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()

        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        print("ChronosMatch stopped.")


if __name__ == "__main__":
    main()
