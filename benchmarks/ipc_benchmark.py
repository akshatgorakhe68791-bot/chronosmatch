
import multiprocessing as mp
import os
import time
from pathlib import Path

from ipc.ring_buffer import MMapRingBuffer

TOTAL_ORDERS = 1_000_000
CAPACITY = 65536
BUFFER_FILE = "benchmark_ring.dat"


def producer(start_event, result_queue):
    with MMapRingBuffer(
        path=BUFFER_FILE,
        capacity=CAPACITY,
        create=False,
    ) as ring:

        start_event.wait()
        start = time.perf_counter()

        for order_id in range(1, TOTAL_ORDERS + 1):
            while not ring.write_order(
                order_id=order_id,
                side="B" if order_id % 2 else "S",
                price=150.00,
                quantity=100,
                timestamp=time.perf_counter_ns(),
            ):
                time.sleep(0)

        elapsed = time.perf_counter() - start
        result_queue.put(("producer", elapsed))


def consumer(start_event, result_queue):
    with MMapRingBuffer(
        path=BUFFER_FILE,
        capacity=CAPACITY,
        create=False,
    ) as ring:

        start_event.wait()
        start = time.perf_counter()

        expected_id = 1
        errors = 0

        while expected_id <= TOTAL_ORDERS:
            order = ring.read_order()

            if order is None:
                time.sleep(0)
                continue

            if order["order_id"] != expected_id:
                errors += 1

            expected_id += 1

        elapsed = time.perf_counter() - start

        result_queue.put(
            ("consumer", elapsed, errors)
        )


def main():
    print("=" * 65)
    print("       CHRONOSMATCH 1 MILLION ORDER IPC BENCHMARK")
    print("=" * 65)

    # Create shared mmap once, before starting processes.
    with MMapRingBuffer(
        path=BUFFER_FILE,
        capacity=CAPACITY,
        create=True,
    ):
        pass

    ctx = mp.get_context("spawn")
    start_event = ctx.Event()
    result_queue = ctx.Queue()

    producer_process = ctx.Process(
        target=producer,
        args=(start_event, result_queue),
    )

    consumer_process = ctx.Process(
        target=consumer,
        args=(start_event, result_queue),
    )

    consumer_process.start()
    producer_process.start()

    start_event.set()

    producer_process.join()
    consumer_process.join()

    results = {}

    while not result_queue.empty():
        result = result_queue.get()
        results[result[0]] = result[1:]

    producer_elapsed = results["producer"][0]
    consumer_elapsed, errors = results["consumer"]

    print(f"Orders Sent      : {TOTAL_ORDERS:,}")
    print(f"Orders Received  : {TOTAL_ORDERS:,}")
    print(f"Sequence Errors  : {errors:,}")
    print(f"Producer Time    : {producer_elapsed:.3f} sec")
    print(f"Consumer Time    : {consumer_elapsed:.3f} sec")
    print(
        f"Consumer Rate    : "
        f"{TOTAL_ORDERS / consumer_elapsed:,.0f} orders/sec"
    )

    if errors == 0:
        print("\nIPC SEQUENCE VALIDATION: PASSED")
    else:
        print("\nIPC SEQUENCE VALIDATION: FAILED")

    Path(BUFFER_FILE).unlink(missing_ok=True)


if __name__ == "__main__":
    mp.freeze_support()
    main()
