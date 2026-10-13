
import curses
import time
from collections import deque


class TerminalDashboard:
    def __init__(self):
        self.orders = 0
        self.trades = 0
        self.throughput = 0.0
        self.best_bid = None
        self.best_ask = None
        self.bid_count = 0
        self.ask_count = 0
        self.avg_latency_us = 0.0
        self.avg_matching_us = 0.0
        self.saved_trades = 0
        self.whale_alerts = deque(maxlen=5)

    def update(self, stats):
        self.orders = stats.get("orders", self.orders)
        self.trades = stats.get("trades", self.trades)
        self.throughput = stats.get("throughput", self.throughput)
        self.best_bid = stats.get("best_bid", self.best_bid)
        self.best_ask = stats.get("best_ask", self.best_ask)
        self.bid_count = stats.get("bids", self.bid_count)
        self.ask_count = stats.get("asks", self.ask_count)
        self.avg_latency_us = stats.get(
            "avg_latency_us", self.avg_latency_us
        )
        self.avg_matching_us = stats.get(
            "avg_matching_us", self.avg_matching_us
        )
        self.saved_trades = stats.get(
            "saved_trades", self.saved_trades
        )

        alert = stats.get("whale_alert")
        if alert:
            self.whale_alerts.appendleft(alert)

    def _draw(self, screen):
        screen.erase()
        screen.nodelay(True)

        height, width = screen.getmaxyx()

        def line(row, text):
            if row < height and width > 1:
                try:
                    screen.addnstr(
                        row, 2, str(text), max(0, width - 3)
                    )
                except curses.error:
                    pass

        line(1, "=" * 58)
        line(2, "        CHRONOSMATCH LIVE TRADING DASHBOARD")
        line(3, "=" * 58)

        line(5, f"Orders Processed : {self.orders:,}")
        line(6, f"Trades Executed  : {self.trades:,}")
        line(7, f"Throughput       : {self.throughput:,.0f} orders/sec")
        line(8, f"SQLite Saved     : {self.saved_trades:,}")

        line(10, "-" * 58)
        line(11, "ORDER BOOK")
        line(12, f"Best Bid         : {self.best_bid}")
        line(13, f"Best Ask         : {self.best_ask}")
        line(14, f"Bid Orders       : {self.bid_count:,}")
        line(15, f"Ask Orders       : {self.ask_count:,}")

        line(17, "-" * 58)
        line(18, "LATENCY")
        line(19, f"Average E2E      : {self.avg_latency_us:,.2f} us")
        line(20, f"Average Matching : {self.avg_matching_us:,.2f} us")

        line(22, "-" * 58)
        line(23, "WHALE ALERTS")

        if not self.whale_alerts:
            line(24, "No whale orders detected")
        else:
            for i, alert in enumerate(self.whale_alerts):
                line(24 + i, alert)

        line(30, "Press Q to quit")
        screen.refresh()

    def run(self, stats_provider=None):
        def loop(screen):
            curses.curs_set(0)
            screen.nodelay(True)

            while True:
                if stats_provider is not None:
                    stats = stats_provider()
                    if stats:
                        self.update(stats)

                self._draw(screen)

                key = screen.getch()
                if key in (ord("q"), ord("Q")):
                    break

                time.sleep(0.2)

        curses.wrapper(loop)


if __name__ == "__main__":
    dashboard = TerminalDashboard()

    dashboard.update({
        "orders": 10000,
        "trades": 7668,
        "throughput": 80911,
        "best_bid": {"price": 150.01, "quantity": 10},
        "best_ask": {"price": 150.04, "quantity": 25},
        "bids": 988,
        "asks": 1025,
        "avg_latency_us": 13670892.99,
        "avg_matching_us": 3.83,
        "saved_trades": 7668,
        "whale_alert": "BUY 500 @ $150.05",
    })

    dashboard.run()
