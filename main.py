
import argparse
import subprocess
import sys
import time
from pathlib import Path

BUFFER_FILE = Path("chronosmatch_ring.dat")
STATS_FILE = Path("dashboard/live_stats.json")
DONE_FILE = Path("producer_done.signal")
LOG_DIR = Path("logs")


def launch_process(name, command):
    log_path = LOG_DIR / f"{name}.log"
    log_file = open(log_path, "w", encoding="utf-8", buffering=1)

    process = subprocess.Popen(
        command,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )

    return process, log_file


def main():
    parser = argparse.ArgumentParser(
        description="ChronosMatch Trading Engine Launcher"
    )
    parser.add_argument("--orders", type=int, default=20000)
    parser.add_argument("--rate", type=int, default=5000)
    args = parser.parse_args()

    if args.orders <= 0 or args.rate <= 0:
        parser.error("--orders and --rate must be positive")

    print("=" * 60)
    print("           CHRONOSMATCH TRADING ENGINE")
    print("=" * 60)
    print(f"Orders : {args.orders:,}")
    print(f"Rate   : {args.rate:,} orders/sec")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if DONE_FILE.exists():
       DONE_FILE.unlink()

    if BUFFER_FILE.exists():
        BUFFER_FILE.unlink()

    if STATS_FILE.exists():
        STATS_FILE.unlink()

    processes = []
    log_files = []

    try:
        consumer, log_file = launch_process(
            "consumer",
            [sys.executable, "-u", "-m", "engine.consumer"],
        )
        processes.append(consumer)
        log_files.append(log_file)
        print(f"Consumer launched. PID: {consumer.pid}")

        time.sleep(1)

        producer, log_file = launch_process(
            "producer",
            [
                sys.executable, "-u", "-m",
                "simulator.market_firehose",
                "--orders", str(args.orders),
                "--rate", str(args.rate),
            ],
        )
        processes.append(producer)
        log_files.append(log_file)
        print(f"Producer launched. PID: {producer.pid}")

        time.sleep(1)

        dashboard, log_file = launch_process(
            "dashboard",
            [sys.executable, "-u", "-m", "dashboard.run_dashboard"],
        )
        processes.append(dashboard)
        log_files.append(log_file)
        print(f"Dashboard launched. PID: {dashboard.pid}")

        print("\nChronosMatch is running.")
        print("Press Ctrl+C here to stop launched processes.")

        while producer.poll() is None:
            time.sleep(0.5)

        print(f"\nProducer finished. Exit code: {producer.returncode}")
        print("Waiting for Consumer to drain the buffer...")

        consumer.wait(timeout=60)

        print("Consumer finished successfully.")
        print("Consumer log: logs/consumer.log")

        print("Dashboard is still running.")
        print("Press Ctrl+C to stop Dashboard.")

        while dashboard.poll() is None:
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
                process.wait()

        for log_file in log_files:
            log_file.close()

        print("ChronosMatch stopped.")


if __name__ == "__main__":
    main()
