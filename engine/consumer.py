
import os
import time
from ipc.layout import ORDER_SIZE
from pathlib import Path

from storage.trade_ledger import TradeLedger
from ipc.ring_buffer import MMapRingBuffer
from engine.matching_engine import MatchingEngine
from dashboard.live_stats import publish_stats

BUFFER_FILE = "chronosmatch_ring.dat"
DONE_FILE = Path("producer_done.signal")

CAPACITY = 65536
STATS_INTERVAL_SECONDS = 1.0
WHALE_THRESHOLD = 500


def main():
    print("=" * 65)
    print("       ChronosMatch LIVE Cython Matching Engine")
    print("=" * 65)

    print(f"Consumer PID : {os.getpid()}")
    print("Waiting for mmap ring buffer...")

    expected_size = 16 + CAPACITY * ORDER_SIZE

    while (
        not os.path.exists(BUFFER_FILE)
        or os.path.getsize(BUFFER_FILE) != expected_size
    ):
        time.sleep(0.05)

    buffer = MMapRingBuffer(
        path=BUFFER_FILE,
        capacity=CAPACITY,
        create=False,
    )

    engine = MatchingEngine()
    ledger = TradeLedger("storage/chronosmatch.db")
    ledger.start()

    print("SQLite Trade Ledger initialized successfully.")
    print("Connected to mmap ring buffer.")
    print("Cython Matching Engine initialized successfully.")
    print("Processing LIVE market orders...")

    total_orders = 0
    total_trades = 0
    total_latency_ns = 0
    total_matching_ns = 0

    min_latency_ns = None
    max_latency_ns = 0
    last_trade = None
    latest_whale_alert = None

    start_time = time.perf_counter()
    last_publish_time = start_time

    try:
        while True:
            order = buffer.read_order()

            if order is None:
                # Stop only after producer is done AND buffer is empty.
                if DONE_FILE.exists() and buffer.size() == 0:
                    print("\nProducer completed and buffer drained.")
                    break

                time.sleep(0.0001)
                continue

            if order["quantity"] >= WHALE_THRESHOLD:
                latest_whale_alert = (
                    f"WHALE {order['side']} | "
                    f"Order {order['order_id']} | "
                    f"Qty {order['quantity']} | "
                    f"${order['price']:.2f}"
                )

            receive_ns = time.perf_counter_ns()
            latency_ns = max(0, receive_ns - order["timestamp"])

            total_latency_ns += latency_ns
            min_latency_ns = (
                latency_ns if min_latency_ns is None
                else min(min_latency_ns, latency_ns)
            )
            max_latency_ns = max(max_latency_ns, latency_ns)

            matching_start_ns = time.perf_counter_ns()

            trades = engine.add_order(
                order["order_id"],
                order["side"],
                order["price"],
                order["quantity"],
            )

            matching_end_ns = time.perf_counter_ns()
            total_matching_ns += matching_end_ns - matching_start_ns
            total_orders += 1

            if trades:
                total_trades += len(trades)
                last_trade = trades[-1]

                for trade in trades:
                    ledger.record_trade(trade)

            now = time.perf_counter()

            if now - last_publish_time >= STATS_INTERVAL_SECONDS:
                elapsed = now - start_time
                stats = engine.stats()

                throughput = total_orders / elapsed if elapsed > 0 else 0
                avg_latency_us = total_latency_ns / total_orders / 1000
                avg_matching_us = total_matching_ns / total_orders / 1000

                publish_stats({
                    "orders": total_orders,
                    "trades": total_trades,
                    "throughput": throughput,
                    "best_bid": engine.best_bid(),
                    "best_ask": engine.best_ask(),
                    "bids": stats["bids"],
                    "asks": stats["asks"],
                    "avg_latency_us": avg_latency_us,
                    "avg_matching_us": avg_matching_us,
                    "saved_trades": ledger.saved_count,
                    "whale_alert": latest_whale_alert,
                })

                print("\n" + "=" * 65)
                print("          CHRONOSMATCH LIVE STATISTICS")
                print("=" * 65)
                print(f"Orders Processed : {total_orders:,}")
                print(f"Trades Executed  : {total_trades:,}")
                print(f"Throughput       : {throughput:,.0f} orders/sec")
                print(f"Buffer Depth     : {buffer.size():,}")
                print(f"Average E2E      : {avg_latency_us:,.2f} us")
                print(f"Minimum E2E      : {min_latency_ns / 1000:,.2f} us")
                print(f"Maximum E2E      : {max_latency_ns / 1000:,.2f} us")
                print(f"Avg Cython Match : {avg_matching_us:,.2f} us")
                print(f"Best Bid         : {engine.best_bid()}")
                print(f"Best Ask         : {engine.best_ask()}")
                print(
                    f"Order Book       : "
                    f"{stats['bids']} bids / {stats['asks']} asks"
                )

                if last_trade:
                    print(
                        f"Last Trade       : "
                        f"BUY {last_trade['buy_order_id']} / "
                        f"SELL {last_trade['sell_order_id']} | "
                        f"{last_trade['quantity']} @ "
                        f"${last_trade['price']:.2f}"
                    )

                print("=" * 65)
                last_publish_time = now

    except KeyboardInterrupt:
        print("\nConsumer stopped manually.")

    finally:
        elapsed = time.perf_counter() - start_time
        throughput = total_orders / elapsed if elapsed > 0 else 0

        final_stats = engine.stats()

        print("\n" + "=" * 65)
        print("          FINAL SESSION STATISTICS")
        print("=" * 65)
        print(f"Total Orders        : {total_orders:,}")
        print(f"Total Trades        : {total_trades:,}")
        print(f"Throughput          : {throughput:,.0f} orders/sec")

        if total_orders:
            print(
                f"Average E2E         : "
                f"{total_latency_ns / total_orders / 1000:,.2f} us"
            )
            print(
                f"Avg Cython Match    : "
                f"{total_matching_ns / total_orders / 1000:,.2f} us"
            )

        print(f"Engine Stats        : {final_stats}")
        print(f"Best Bid            : {engine.best_bid()}")
        print(f"Best Ask            : {engine.best_ask()}")

        ledger.close()
        saved_trades = ledger.saved_count
        print(f"SQLite Trades Saved : {saved_trades:,}")
        buffer.close()

        publish_stats({
            "orders": total_orders,
            "trades": total_trades,
            "throughput": throughput,
            "best_bid": engine.best_bid(),
            "best_ask": engine.best_ask(),
            "bids": final_stats["bids"],
            "asks": final_stats["asks"],
            "avg_latency_us": (
                total_latency_ns / total_orders / 1000
                if total_orders else 0
            ),
            "avg_matching_us": (
                total_matching_ns / total_orders / 1000
                if total_orders else 0
            ),
            "saved_trades": saved_trades,
            "whale_alert": latest_whale_alert,
        })

        print("=" * 65)
        print("Consumer shutdown complete.")


if __name__ == "__main__":
    main()
