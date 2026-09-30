import os
import time

from ipc.ring_buffer import MMapRingBuffer


BUFFER_FILE = "test_ring.dat"
CAPACITY = 8


def cleanup():
    if os.path.exists(BUFFER_FILE):
        os.remove(BUFFER_FILE)


def main():
    cleanup()

    print("=" * 55)
    print("       ChronosMatch Zero-Copy IPC Test")
    print("=" * 55)

    buffer = MMapRingBuffer(
        path=BUFFER_FILE,
        capacity=CAPACITY,
        create=True,
    )

    timestamp = time.perf_counter_ns()

    print("\nWriting BUY order...")

    success = buffer.write_order(
        order_id=1001,
        side="B",
        price=150.25,
        quantity=100,
        timestamp=timestamp,
    )

    print("Write successful:", success)
    print("Orders currently in buffer:", buffer.size())

    print("\nReading order...")

    order = buffer.read_order()

    print("Order ID :", order["order_id"])
    print("Side     :", order["side"])
    print("Price    :", order["price"])
    print("Quantity :", order["quantity"])
    print("Timestamp:", order["timestamp"])

    print("\nOrders remaining:", buffer.size())

    buffer.close()

    cleanup()

    print("\nRing Buffer Test: PASSED")
    print("=" * 55)


if __name__ == "__main__":
    main()