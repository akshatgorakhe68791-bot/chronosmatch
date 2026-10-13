
import os
import time

from storage.trade_ledger import TradeLedger
from ipc.ring_buffer import MMapRingBuffer
from engine.matching_engine import MatchingEngine
from dashboard.live_stats import publish_stats

BUFFER_FILE = "chronosmatch_ring.dat"
CAPACITY = 65536
REPORT_INTERVAL = 10000
WHALE_THRESHOLD = 500
latest_whale_alert = None


def main():
    print("=" * 65)
    print("       ChronosMatch LIVE Cython Matching Engine")
    print("=" * 65)

    print(f"Consumer PID : {os.getpid()}")
    print("Waiting for mmap ring buffer...")

    while not os.path.exists(BUFFER_FILE):
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

    print("\nConnected to mmap ring buffer.")
    print("Cython Matching Engine initialized successfully.")
    print("Processing LIVE market orders...")
    print("Press Ctrl+C to stop.\n")

    total_orders = 0
    total_trades = 0
    total_latency_ns = 0

    min_latency_ns = None
    max_latency_ns = 0

    total_matching_ns = 0
    last_trade = None

    start_time = time.perf_counter()

    try:
        while True:
            order = buffer.read_order()

            if order is None:
                time.sleep(0.0001)
                continue
            if order["quantity"] >= WHALE_THRESHOLD:
               latest_whale_alert = (
                     f"WHALE {order['side']} | "
                     f"Order {order['order_id']} | "
                     f"Qty {order['quantity']} | "
                     f"${order['price']:.2f}"
                )

            # End-to-end latency includes time spent waiting
            # inside the shared ring buffer.
            receive_ns = time.perf_counter_ns()
            latency_ns = max(
                0,
                receive_ns - order["timestamp"]
            )

            total_latency_ns += latency_ns

            if min_latency_ns is None:
                min_latency_ns = latency_ns
            else:
                min_latency_ns = min(
                    min_latency_ns,
                    latency_ns
                )

            max_latency_ns = max(
                max_latency_ns,
                latency_ns
            )

            # Measure Cython matching call separately.
            matching_start_ns = time.perf_counter_ns()

            trades = engine.add_order(
                order["order_id"],
                order["side"],
                order["price"],
                order["quantity"],
            )

            matching_end_ns = time.perf_counter_ns()

            total_matching_ns += (
                matching_end_ns - matching_start_ns
            )

            total_orders += 1

            if trades:
                total_trades += len(trades)
                last_trade = trades[-1]

                for trade in trades:
                    ledger.record_trade(trade)

            if total_orders % REPORT_INTERVAL == 0:
                elapsed = time.perf_counter() - start_time

                throughput = (
                    total_orders / elapsed
                    if elapsed > 0 else 0
                )

                avg_latency_us = (
                    total_latency_ns / total_orders / 1000
                )

                avg_matching_us = (
                    total_matching_ns / total_orders / 1000
                )

                stats = engine.stats()
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

                print("=" * 65)
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
                    f"{stats['bids']} bids / "
                    f"{stats['asks']} asks"
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

    except KeyboardInterrupt:
        print("\n\nConsumer stopped.")

    finally:
        elapsed = time.perf_counter() - start_time

        print("\n" + "=" * 65)
        print("          FINAL SESSION STATISTICS")
        print("=" * 65)

        print(f"Total Orders     : {total_orders:,}")
        print(f"Total Trades     : {total_trades:,}")

        if elapsed > 0:
            print(
                f"Throughput       : "
                f"{total_orders / elapsed:,.0f} orders/sec"
            )

        if total_orders > 0:
            print(
                f"Average E2E      : "
                f"{total_latency_ns / total_orders / 1000:,.2f} us"
            )

            print(
                f"Avg Cython Match : "
                f"{total_matching_ns / total_orders / 1000:,.2f} us"
            )

        print(f"Engine Stats     : {engine.stats()}")
        print(f"Best Bid         : {engine.best_bid()}")
        print(f"Best Ask         : {engine.best_ask()}")
        
        ledger.close()
        print(f"SQLite Trades Saved : {ledger.saved_count:,}")
        buffer.close()

        final_stats = engine.stats()

        publish_stats({
             "orders": total_orders,
             "trades": total_trades,
             "throughput": 0,
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
            "saved_trades": ledger.saved_count,
        })


if __name__ == "__main__":
    main()
