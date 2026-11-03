
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
        self.last_whale_alert = None
        self.last_update = None

    def update(self, stats):
        if not stats:
            return

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

        if alert and alert != self.last_whale_alert:
            self.whale_alerts.appendleft(str(alert))
            self.last_whale_alert = alert

        self.last_update = time.strftime("%H:%M:%S")

    @staticmethod
    def format_price(value):
        if value is None:
            return "N/A"

        if isinstance(value, dict):
            price = value.get("price", 0)
            quantity = value.get("quantity", 0)
            return f"${price:,.2f}  (Qty: {quantity:,})"

        return str(value)

    @staticmethod
    def safe_add(screen, row, col, message, width, color=0):
        height, screen_width = screen.getmaxyx()

        if row < 0 or row >= height or col >= screen_width:
            return

        available = min(width, screen_width - col - 1)

        if available <= 0:
            return

        try:
            screen.addnstr(
                row, col, str(message), available, color
            )
        except curses.error:
            pass

    def setup_colors(self):
        if not curses.has_colors():
            return

        curses.start_color()

        try:
            curses.use_default_colors()
        except curses.error:
            pass

        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_CYAN, -1)
        curses.init_pair(4, curses.COLOR_YELLOW, -1)
        curses.init_pair(5, curses.COLOR_WHITE, -1)

    def draw(self, screen):
        screen.erase()

        height, width = screen.getmaxyx()

        green = curses.color_pair(1) | curses.A_BOLD
        red = curses.color_pair(2) | curses.A_BOLD
        cyan = curses.color_pair(3) | curses.A_BOLD
        yellow = curses.color_pair(4) | curses.A_BOLD
        normal = curses.color_pair(5)

        self.safe_add(
            screen, 0, 2,
            "=" * 70, width - 4, cyan
        )

        self.safe_add(
            screen, 1, 2,
            "CHRONOSMATCH | LIVE TRADING ENGINE",
            width - 4, cyan
        )

        self.safe_add(
            screen, 2, 2,
            "=" * 70, width - 4, cyan
        )

        self.safe_add(
            screen, 4, 2,
            "MARKET OVERVIEW", width - 4, yellow
        )

        self.safe_add(
            screen, 5, 4,
            f"Orders Processed : {self.orders:,}",
            width - 6, normal
        )

        self.safe_add(
            screen, 6, 4,
            f"Trades Executed  : {self.trades:,}",
            width - 6, normal
        )

        self.safe_add(
            screen, 7, 4,
            f"Throughput       : {self.throughput:,.0f} orders/sec",
            width - 6, green
        )

        self.safe_add(
            screen, 8, 4,
            f"SQLite Saved     : {self.saved_trades:,}",
            width - 6, normal
        )

        self.safe_add(
            screen, 10, 2,
            "ORDER BOOK", width - 4, yellow
        )

        self.safe_add(
            screen, 11, 4,
            f"Best Bid : {self.format_price(self.best_bid)}",
            width - 6, green
        )

        self.safe_add(
            screen, 12, 4,
            f"Best Ask : {self.format_price(self.best_ask)}",
            width - 6, red
        )

        self.safe_add(
            screen, 13, 4,
            f"Bid Orders : {self.bid_count:,}",
            width - 6, normal
        )

        self.safe_add(
            screen, 14, 4,
            f"Ask Orders : {self.ask_count:,}",
            width - 6, normal
        )

        self.safe_add(
            screen, 16, 2,
            "LATENCY MONITOR", width - 4, yellow
        )

        self.safe_add(
            screen, 17, 4,
            f"Average E2E      : {self.avg_latency_us:,.2f} us",
            width - 6, normal
        )

        self.safe_add(
            screen, 18, 4,
            f"Average Matching : {self.avg_matching_us:,.2f} us",
            width - 6, green
        )

        self.safe_add(
            screen, 20, 2,
            "WHALE ALERTS (Latest 5)", width - 4, yellow
        )

        if not self.whale_alerts:
            self.safe_add(
                screen, 21, 4,
                "No whale orders detected",
                width - 6, normal
            )
        else:
            for index, alert in enumerate(self.whale_alerts):
                self.safe_add(
                    screen, 21 + index, 4,
                    f"> {alert}", width - 6, red
                )

        self.safe_add(
            screen, height - 3, 2,
            f"Last Update: {self.last_update or 'Waiting for data'}",
            width - 4, cyan
        )

        self.safe_add(
            screen, height - 2, 2,
            "Press Q to quit dashboard",
            width - 4, yellow
        )

        screen.refresh()

    def run(self, stats_provider=None):
        def loop(screen):
            curses.curs_set(0)
            screen.nodelay(True)

            self.setup_colors()

            while True:
                if stats_provider:
                    try:
                        stats = stats_provider()
                        self.update(stats)
                    except (OSError, ValueError):
                        pass

                self.draw(screen)

                key = screen.getch()

                if key in (ord("q"), ord("Q")):
                    break

                time.sleep(0.2)

        curses.wrapper(loop)


if __name__ == "__main__":
    dashboard = TerminalDashboard()

    dashboard.update({
        "orders": 20000,
        "trades": 15459,
        "throughput": 5000,
        "best_bid": {"price": 150.01, "quantity": 10},
        "best_ask": {"price": 150.04, "quantity": 25},
        "bids": 988,
        "asks": 1025,
        "avg_latency_us": 1506.28,
        "avg_matching_us": 1.73,
        "saved_trades": 15459,
        "whale_alert": "WHALE BUY | Order 1001 | Qty 500 | $150.05",
    })

    dashboard.run()
