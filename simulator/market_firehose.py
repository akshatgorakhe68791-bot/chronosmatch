
import asyncio
import argparse
import random
import time

from ipc.ring_buffer import MMapRingBuffer


BUFFER_FILE = "chronosmatch_ring.dat"
CAPACITY = 65536


async def market_firehose(total_orders, target_rate):
    rng = random.Random(42)

    with MMapRingBuffer(
        path=BUFFER_FILE,
        capacity=CAPACITY,
        create=True,
    ) as ring:

        print("=" * 60)
        print("       CHRONOSMATCH ASYNC MARKET FIREHOSE")
        print("=" * 60)
        print(f"Orders to generate : {total_orders:,}")
        print(f"Target rate        : {target_rate:,}/sec")
        print("Waiting for consumer? Start it in another terminal.")
        print()

        sent = 0
        start = time.perf_counter()
        next_report = start + 1.0

        while sent < total_orders:
            # Generate a bounded batch before yielding.
            for _ in range(min(512, total_orders - sent)):
                order_id = sent + 1
                side = "B" if rng.getrandbits(1) else "S"
                price = rng.randint(14990, 15010) / 100.0
                quantity = rng.choice((10, 25, 50, 100, 200, 500))

                while not ring.write_order(
                    order_id=order_id,
                    side=side,
                    price=price,
                    quantity=quantity,
                    timestamp=time.perf_counter_ns(),
                ):
                    await asyncio.sleep(0.0001)

                sent += 1

            elapsed = time.perf_counter() - start

            # Pace average generation toward the requested target.
            target_elapsed = sent / target_rate

            if target_elapsed > elapsed:
                await asyncio.sleep(target_elapsed - elapsed)
            else:
                await asyncio.sleep(0)

            now = time.perf_counter()

            if now >= next_report:
                elapsed = now - start
                rate = sent / elapsed

                print(
                    f"Produced: {sent:,} | "
                    f"Rate: {rate:,.0f}/sec | "
                    f"Buffer: {ring.size():,}"
                )

                next_report = now + 1.0

        elapsed = time.perf_counter() - start

        print("\n" + "=" * 60)
        print("MARKET FIREHOSE COMPLETE")
        print("=" * 60)
        print(f"Orders Sent : {sent:,}")
        print(f"Elapsed     : {elapsed:.3f} sec")
        print(f"Actual Rate : {sent / elapsed:,.0f} orders/sec")
        print(f"Buffer Left : {ring.size():,}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--orders",
        type=int,
        default=10000,
    )

    parser.add_argument(
        "--rate",
        type=int,
        default=100000,
    )

    args = parser.parse_args()

    if args.orders <= 0 or args.rate <= 0:
        parser.error("--orders and --rate must be positive")

    asyncio.run(
        market_firehose(args.orders, args.rate)
    )


if __name__ == "__main__":
    main()
