import os
import time

from ipc.ring_buffer import MMapRingBuffer


BUFFER_FILE = "chronosmatch_ring.dat"
CAPACITY = 65536


def main():
    print("=" * 60)
    print("       ChronosMatch LIVE Engine Consumer")
    print("=" * 60)

    print(f"PID: {os.getpid()}")
    print("Waiting for shared mmap buffer...")

    while not os.path.exists(BUFFER_FILE):
        time.sleep(0.1)

    buffer = MMapRingBuffer(
        path=BUFFER_FILE,
        capacity=CAPACITY,
        create=False,
    )

    print("Connected to shared mmap buffer.")
    print("Reading live orders...")
    print("Press Ctrl+C to stop.\n")

    total_orders = 0
    total_latency_ns = 0
    min_latency_ns = None
    max_latency_ns = 0

    start_time = time.perf_counter()

    try:
        while True:
            order = buffer.read_order()

            if order is None:
                time.sleep(0)
                continue

            exit_timestamp = time.perf_counter_ns()

            latency_ns = (
                exit_timestamp - order["timestamp"]
            )

            total_orders += 1
            total_latency_ns += latency_ns

            if min_latency_ns is None:
                min_latency_ns = latency_ns
            else:
                min_latency_ns = min(
                    min_latency_ns,
                    latency_ns,
                )

            max_latency_ns = max(
                max_latency_ns,
                latency_ns,
            )

            elapsed = time.perf_counter() - start_time

            throughput = (
                total_orders / elapsed
                if elapsed > 0
                else 0
            )

            avg_latency_us = (
                total_latency_ns
                / total_orders
                / 1000
            )

            print(
                f"\rConsumed: {total_orders:,} | "
                f"Last ID: {order['order_id']:,} | "
                f"{order['side']} "
                f"${order['price']:.2f} "
                f"x {order['quantity']} | "
                f"Latency: {latency_ns / 1000:.2f} us | "
                f"Avg: {avg_latency_us:.2f} us | "
                f"Rate: {throughput:,.0f}/sec",
                end="",
                flush=True,
            )

    except KeyboardInterrupt:
        print("\n\nConsumer stopped.")

        if total_orders:
            print("\n--- Session Statistics ---")
            print(f"Orders     : {total_orders:,}")
            print(
                f"Average    : "
                f"{total_latency_ns / total_orders / 1000:.2f} us"
            )
            print(
                f"Minimum    : "
                f"{min_latency_ns / 1000:.2f} us"
            )
            print(
                f"Maximum    : "
                f"{max_latency_ns / 1000:.2f} us"
            )

    finally:
        buffer.close()


if __name__ == "__main__":
    main()