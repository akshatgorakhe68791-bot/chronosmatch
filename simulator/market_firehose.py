
import asyncio
import argparse
import random
import time
from pathlib import Path

from ipc.ring_buffer import MMapRingBuffer


BUFFER_FILE = "chronosmatch_ring.dat"
CAPACITY = 65536
DONE_FILE = Path("producer_done.signal")


async def market_firehose(total_orders, target_rate):
    if DONE_FILE.exists():
        DONE_FILE.unlink()

    rng = random.Random()

    buffer = MMapRingBuffer(
        path=BUFFER_FILE,
        capacity=CAPACITY,
        create=True,
    )

    sent = 0
    start_time = time.perf_counter()
    next_report = 2048

    print("=" * 60)
    print("       CHRONOSMATCH ASYNC MARKET FIREHOSE")
    print("=" * 60)
    print(f"Orders to generate : {total_orders:,}")
    print(f"Target rate        : {target_rate:,}/sec")

    interval = 1.0 / target_rate

    try:
        while sent < total_orders:
            batch_start = time.perf_counter()

            batch_size = min(512, total_orders - sent)

            for _ in range(batch_size):
                order = {
                    "order_id": sent + 1,
                    "side": rng.choice(["B", "S"]),
                    "price": round(rng.uniform(149.90, 150.10), 2),
                    "quantity": rng.choice(
                        [10, 25, 50, 100, 200, 500]
                    ),
                    "timestamp": time.perf_counter_ns(),
                }

                while not buffer.write_order(
   		            order["order_id"],
    		        order["side"],
    		        order["price"],
   		            order["quantity"],
    		        order["timestamp"],
                ):
                    await asyncio.sleep(0.0001)

                sent += 1

                if sent >= next_report:
                    elapsed = time.perf_counter() - start_time
                    rate = sent / elapsed if elapsed else 0

                    print(
                        f"Produced: {sent:,} | "
                        f"Rate: {rate:,.0f}/sec | "
                        f"Buffer: {buffer.size():,}"
                    )
                    next_report += 2048

                await asyncio.sleep(interval)

            batch_elapsed = time.perf_counter() - batch_start

            if batch_elapsed < 0:
                await asyncio.sleep(0)

        elapsed = time.perf_counter() - start_time
        actual_rate = sent / elapsed if elapsed else 0

        print("\n" + "=" * 60)
        print("MARKET FIREHOSE COMPLETE")
        print("=" * 60)
        print(f"Orders Sent : {sent:,}")
        print(f"Elapsed     : {elapsed:.3f} sec")
        print(f"Actual Rate : {actual_rate:,.0f} orders/sec")
        print(f"Buffer Left : {buffer.size():,}")

        # Signal consumer that no more orders will be written.
        DONE_FILE.write_text("done", encoding="utf-8")
        print("Producer completion signal created.")

    finally:
        buffer.close()


def main():
    parser = argparse.ArgumentParser(
        description="ChronosMatch Async Market Firehose"
    )

    parser.add_argument("--orders", type=int, default=20000)
    parser.add_argument("--rate", type=int, default=5000)

    args = parser.parse_args()

    if args.orders <= 0 or args.rate <= 0:
        parser.error("--orders and --rate must be positive")

    asyncio.run(market_firehose(args.orders, args.rate))


if __name__ == "__main__":
    main()
