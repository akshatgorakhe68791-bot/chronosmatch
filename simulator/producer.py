import os
import random
import time

from ipc.ring_buffer import MMapRingBuffer


BUFFER_FILE = "chronosmatch_ring.dat"
CAPACITY = 65536


def main():
    print("=" * 60)
    print("       ChronosMatch LIVE Market Producer")
    print("=" * 60)

    # Producer creates/resets the shared mmap file.
    buffer = MMapRingBuffer(
        path=BUFFER_FILE,
        capacity=CAPACITY,
        create=True,
    )

    print(f"PID      : {os.getpid()}")
    print(f"Buffer   : {BUFFER_FILE}")
    print(f"Capacity : {CAPACITY}")
    print("\nStreaming market orders...")
    print("Press Ctrl+C to stop.\n")

    order_id = 1

    try:
        while True:
            side = random.choice(("B", "S"))

            # Prices clustered around $150 so crossing orders
            # will be common when the matching engine is added.
            price = round(
                random.uniform(149.90, 150.10),
                2,
            )

            quantity = random.choice(
                (10, 25, 50, 100, 200, 500)
            )

            timestamp = time.perf_counter_ns()

            success = buffer.write_order(
                order_id=order_id,
                side=side,
                price=price,
                quantity=quantity,
                timestamp=timestamp,
            )

            if success:
                print(
                    f"\rProduced: {order_id:,} | "
                    f"Side: {side} | "
                    f"Price: ${price:.2f} | "
                    f"Qty: {quantity:<4} | "
                    f"Buffer: {buffer.size():,}",
                    end="",
                    flush=True,
                )

                order_id += 1

            else:
                # Consumer has fallen behind.
                # Yield briefly instead of overwriting unread orders.
                time.sleep(0.0001)

    except KeyboardInterrupt:
        print("\n\nProducer stopped.")

    finally:
        buffer.close()


if __name__ == "__main__":
    main()