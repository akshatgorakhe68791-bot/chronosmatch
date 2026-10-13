
import queue
import sqlite3
import threading
from pathlib import Path


class TradeLedger:
    def __init__(self, db_path="storage/chronosmatch.db"):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(
            parents=True, exist_ok=True
        )

        self.trade_queue = queue.Queue(maxsize=100000)
        self.worker = None
        self.started = False
        self.saved_count = 0
        self.worker_error = None

    def _worker_loop(self):
        try:
            connection = sqlite3.connect(self.db_path)
            connection.execute("PRAGMA journal_mode=WAL")

            connection.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    buy_order_id INTEGER NOT NULL,
                    sell_order_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.commit()

            batch = []

            while True:
                item = self.trade_queue.get()

                if item is None:
                    if batch:
                        self._save_batch(connection, batch)
                    self.trade_queue.task_done()
                    break

                batch.append(item)
                self.trade_queue.task_done()

                if len(batch) >= 500:
                    self._save_batch(connection, batch)
                    batch.clear()

            connection.close()

        except Exception as exc:
            self.worker_error = exc

    def _save_batch(self, connection, batch):
        connection.executemany(
            """
            INSERT INTO trades (
                buy_order_id,
                sell_order_id,
                price,
                quantity
            )
            VALUES (?, ?, ?, ?)
            """,
            batch,
        )
        connection.commit()
        self.saved_count += len(batch)

    def start(self):
        if self.started:
            return

        self.worker = threading.Thread(
            target=self._worker_loop,
            daemon=False,
        )
        self.worker.start()
        self.started = True

    def record_trade(self, trade):
        if not self.started:
            raise RuntimeError("TradeLedger not started")

        if self.worker_error is not None:
            raise RuntimeError(
                "Trade ledger worker failed"
            ) from self.worker_error

        self.trade_queue.put((
            trade["buy_order_id"],
            trade["sell_order_id"],
            trade["price"],
            trade["quantity"],
        ))

    def close(self):
        if not self.started:
            return

        self.trade_queue.put(None)
        self.worker.join()

        self.started = False

        if self.worker_error is not None:
            raise RuntimeError(
                "Trade ledger worker failed"
            ) from self.worker_error

    def count_trades(self):
        with sqlite3.connect(self.db_path) as connection:
            result = connection.execute(
                "SELECT COUNT(*) FROM trades"
            ).fetchone()

        return result[0]
