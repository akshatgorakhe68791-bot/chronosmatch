
from pathlib import Path

from storage.trade_ledger import TradeLedger


DB_PATH = "storage/test_trades.db"

Path(DB_PATH).unlink(missing_ok=True)

ledger = TradeLedger(DB_PATH)
ledger.start()

for i in range(1, 1001):
    ledger.record_trade({
        "buy_order_id": i,
        "sell_order_id": i + 1000,
        "price": 150.00,
        "quantity": 100,
    })

ledger.close()

count = ledger.count_trades()

print("=" * 55)
print("       CHRONOSMATCH SQLITE LEDGER TEST")
print("=" * 55)
print(f"Expected Trades : 1,000")
print(f"Saved Trades    : {count:,}")

assert count == 1000, "Trade count mismatch"

print("\nSQLITE TRADE LEDGER TEST PASSED")
