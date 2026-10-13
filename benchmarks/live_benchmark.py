
import argparse
import multiprocessing as mp
import time
from pathlib import Path

from ipc.ring_buffer import MMapRingBuffer
from engine.matching_engine import MatchingEngine


BUFFER_FILE = "chronosmatch_live_benchmark.dat"
CAPACITY = 65536


def percentile(values, percent):
    if not values:
        return 0.0

    values = sorted(values)
    index = (len(values) - 1) * percent / 100.0
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    fraction = index - lower

    return (
        values[lower] * (1 - fraction)
        + values[upper] * fraction
    )


def producer(ready_event, start_event, results, total_orders, rate):
    try:
        with MMapRingBuffer(
            path=BUFFER_FILE,
            capacity=CAPACITY,
            create=False,
        ) as ring:

            ready_event.set()

            if not start_event.wait(timeout=30):
                raise TimeoutError("Producer start timed out")

            start = time.perf_counter()
            sent = 0

            while sent < total_orders:
                order_id = sent + 1

                # Deterministic alternating orders.
                side = "B" if order_id % 2 else "S"
                price = 150.00
                quantity = 100

                while not ring.write_order(
                    order_id=order_id,
                    side=side,
                    price=price,
                    quantity=quantity,
                    timestamp=time.perf_counter_ns(),
                ):
                    time.sleep(0)

                sent += 1

                # Pace in batches, not once per order.
                if sent % 100 == 0:
                    target_elapsed = sent / rate
                    actual_elapsed = time.perf_counter() - start

                    if target_elapsed > actual_elapsed:
                        time.sleep(target_elapsed - actual_elapsed)

            elapsed = time.perf_counter() - start

            results.put({
                "type": "producer",
                "sent": sent,
                "elapsed": elapsed,
            })

    except Exception as exc:
        results.put({
            "type": "producer_error",
            "error": repr(exc),
        })
        raise


def consumer(ready_event, start_event, results, total_orders):
    try:
        with MMapRingBuffer(
            path=BUFFER_FILE,
            capacity=CAPACITY,
            create=False,
        ) as ring:

            engine = MatchingEngine()
            ready_event.set()

            if not start_event.wait(timeout=30):
                raise TimeoutError("Consumer start timed out")

            expected_id = 1
            sequence_errors = 0
            e2e_latencies = []
            matching_latencies = []
            trade_count = 0

            start = time.perf_counter()

            while expected_id <= total_orders:
                order = ring.read_order()

                if order is None:
                    time.sleep(0)
                    continue

                received_ns = time.perf_counter_ns()

                e2e_latencies.append(
                    max(0, received_ns - order["timestamp"]) / 1000
                )

                if order["order_id"] != expected_id:
                    sequence_errors += 1

                match_start_ns = time.perf_counter_ns()

                trades = engine.add_order(
                    order["order_id"],
                    order["side"],
                    order["price"],
                    order["quantity"],
                )

                match_end_ns = time.perf_counter_ns()

                matching_latencies.append(
                    (match_end_ns - match_start_ns) / 1000
                )

                trade_count += len(trades)
                expected_id += 1

            elapsed = time.perf_counter() - start

            results.put({
                "type": "consumer",
                "received": expected_id - 1,
                "elapsed": elapsed,
                "sequence_errors": sequence_errors,
                "trades": trade_count,
                "e2e_avg": sum(e2e_latencies) / len(e2e_latencies),
                "e2e_p50": percentile(e2e_latencies, 50),
                "e2e_p95": percentile(e2e_latencies, 95),
                "e2e_p99": percentile(e2e_latencies, 99),
                "match_avg": sum(matching_latencies) / len(matching_latencies),
                "match_p50": percentile(matching_latencies, 50),
                "match_p95": percentile(matching_latencies, 95),
                "match_p99": percentile(matching_latencies, 99),
                "engine_stats": engine.stats(),
                "buffer_left": ring.size(),
            })

    except Exception as exc:
        results.put({
            "type": "consumer_error",
            "error": repr(exc),
        })
        raise


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--orders", type=int, default=20000)
    parser.add_argument("--rate", type=int, default=5000)

    args = parser.parse_args()

    if args.orders <= 0 or args.rate <= 0:
        parser.error("Orders and rate must be positive")

    path = Path(BUFFER_FILE)

    if path.exists():
        path.unlink()

    # Initialize the mmap file exactly once.
    with MMapRingBuffer(
        path=BUFFER_FILE,
        capacity=CAPACITY,
        create=True,
    ):
        pass

    ctx = mp.get_context("spawn")

    producer_ready = ctx.Event()
    consumer_ready = ctx.Event()
    start_event = ctx.Event()
    results_queue = ctx.Queue()

    producer_process = ctx.Process(
        target=producer,
        args=(
            producer_ready,
            start_event,
            results_queue,
            args.orders,
            args.rate,
        ),
    )

    consumer_process = ctx.Process(
        target=consumer,
        args=(
            consumer_ready,
            start_event,
            results_queue,
            args.orders,
        ),
    )

    print("=" * 65)
    print("       CHRONOSMATCH SYNCHRONIZED LIVE BENCHMARK")
    print("=" * 65)
    print(f"Total Orders : {args.orders:,}")
    print(f"Target Rate  : {args.rate:,} orders/sec")
    print()

    consumer_process.start()
    producer_process.start()

    try:
        if not consumer_ready.wait(timeout=30):
            raise TimeoutError("Consumer did not become ready")

        if not producer_ready.wait(timeout=30):
            raise TimeoutError("Producer did not become ready")

        print("Producer Ready : YES")
        print("Consumer Ready : YES")
        print("Starting synchronized benchmark...\n")

        start_event.set()

        # Collect both results before joining processes.
        # This avoids waiting indefinitely if the result
        # queue contains a large serialized message.
        collected = {}

        for _ in range(2):
            result = results_queue.get(timeout=120)
            collected[result["type"]] = result

        producer_process.join(timeout=10)
        consumer_process.join(timeout=10)

        if "producer_error" in collected or "consumer_error" in collected:
            raise RuntimeError(str(collected))

        p = collected["producer"]
        c = collected["consumer"]

        print("=" * 65)
        print("                 FINAL BENCHMARK RESULTS")
        print("=" * 65)

        print(f"Orders Sent        : {p['sent']:,}")
        print(f"Orders Received    : {c['received']:,}")
        print(f"Sequence Errors    : {c['sequence_errors']:,}")
        print(f"Trades Executed    : {c['trades']:,}")
        print(f"Producer Rate      : {p['sent'] / p['elapsed']:,.0f}/sec")
        print(f"Consumer Rate      : {c['received'] / c['elapsed']:,.0f}/sec")
        print(f"Buffer Remaining   : {c['buffer_left']:,}")

        print("\nEND-TO-END LATENCY")
        print(f"Average : {c['e2e_avg']:,.2f} us")
        print(f"P50     : {c['e2e_p50']:,.2f} us")
        print(f"P95     : {c['e2e_p95']:,.2f} us")
        print(f"P99     : {c['e2e_p99']:,.2f} us")

        print("\nCYTHON MATCHING LATENCY")
        print(f"Average : {c['match_avg']:,.2f} us")
        print(f"P50     : {c['match_p50']:,.2f} us")
        print(f"P95     : {c['match_p95']:,.2f} us")
        print(f"P99     : {c['match_p99']:,.2f} us")

        print(f"\nEngine Stats: {c['engine_stats']}")

        passed = (
            p["sent"] == args.orders
            and c["received"] == args.orders
            and c["sequence_errors"] == 0
            and c["buffer_left"] == 0
            and c["engine_stats"]["orders"] == args.orders
        )

        print("\n" + "=" * 65)
        print(
            "SYNCHRONIZED BENCHMARK: "
            + ("PASSED" if passed else "FAILED")
        )
        print("=" * 65)

    finally:
        for process in (producer_process, consumer_process):
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)

        results_queue.close()

        if path.exists():
            path.unlink()


if __name__ == "__main__":
    mp.freeze_support()
    main()
