from engine.matching_engine import MatchingEngine


def print_section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


engine = MatchingEngine()


# ---------------------------------------------------------
# TEST 1: Orders that should NOT match
# ---------------------------------------------------------

print_section("TEST 1 - Add Resting Orders")

trades = engine.add_order(
    1001,
    "B",
    150.00,
    100,
)

print("BUY  1001 ->", trades)

trades = engine.add_order(
    2001,
    "S",
    150.10,
    100,
)

print("SELL 2001 ->", trades)

print("\nBest Bid:", engine.best_bid())
print("Best Ask:", engine.best_ask())


# ---------------------------------------------------------
# TEST 2: Crossing SELL should match BUY
# ---------------------------------------------------------

print_section("TEST 2 - Basic BUY/SELL Match")

trades = engine.add_order(
    2002,
    "S",
    149.95,
    50,
)

print("Incoming SELL:")
print(trades)

assert len(trades) == 1
assert trades[0]["buy_order_id"] == 1001
assert trades[0]["sell_order_id"] == 2002
assert trades[0]["price"] == 150.00
assert trades[0]["quantity"] == 50

print("\nMATCH PASSED")


# ---------------------------------------------------------
# TEST 3: Partial Fill
# ---------------------------------------------------------

print_section("TEST 3 - Partial Fill")

trades = engine.add_order(
    2003,
    "S",
    150.00,
    25,
)

print(trades)

assert len(trades) == 1
assert trades[0]["buy_order_id"] == 1001
assert trades[0]["quantity"] == 25

print("\nPARTIAL FILL PASSED")


# ---------------------------------------------------------
# TEST 4: Price Priority
# ---------------------------------------------------------

print_section("TEST 4 - Price Priority")

engine.add_order(
    1002,
    "B",
    150.05,
    100,
)

engine.add_order(
    1003,
    "B",
    150.08,
    100,
)

trades = engine.add_order(
    2004,
    "S",
    150.00,
    50,
)

print(trades)

assert trades[0]["buy_order_id"] == 1003
assert trades[0]["price"] == 150.08

print("\nPRICE PRIORITY PASSED")


# ---------------------------------------------------------
# TEST 5: Time Priority
# ---------------------------------------------------------

print_section("TEST 5 - Time Priority")

engine2 = MatchingEngine()

engine2.add_order(
    3001,
    "B",
    151.00,
    100,
)

engine2.add_order(
    3002,
    "B",
    151.00,
    100,
)

trades = engine2.add_order(
    4001,
    "S",
    151.00,
    50,
)

print(trades)

assert trades[0]["buy_order_id"] == 3001

print("\nTIME PRIORITY PASSED")


# ---------------------------------------------------------
# FINAL STATUS
# ---------------------------------------------------------

print_section("FINAL ENGINE STATUS")

print("Main Engine Stats:")
print(engine.stats())

print("\nBest Bid:")
print(engine.best_bid())

print("\nBest Ask:")
print(engine.best_ask())

print("\n" + "=" * 60)
print("ALL CYTHON MATCHING ENGINE TESTS PASSED")
print("=" * 60)