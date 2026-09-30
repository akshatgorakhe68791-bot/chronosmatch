import struct

# ---------------------------------------------------------
# ChronosMatch Binary Order Layout
# ---------------------------------------------------------
#
# Every order is stored directly as raw binary data.
#
# Q = Order ID       -> unsigned long long (8 bytes)
# c = Side           -> char (1 byte) [B = Buy, S = Sell]
# d = Price          -> double (8 bytes)
# I = Quantity       -> unsigned int (4 bytes)
# Q = Timestamp      -> unsigned long long (8 bytes)
#
# "<" means little-endian with standard sizes and no
# platform-dependent alignment padding.
# ---------------------------------------------------------

ORDER_FORMAT = "<QcdIQ"

ORDER_STRUCT = struct.Struct(ORDER_FORMAT)

ORDER_SIZE = ORDER_STRUCT.size


def pack_order(order_id, side, price, quantity, timestamp):
    """
    Convert an order into a fixed-size raw binary record.
    """

    if side not in ("B", "S"):
        raise ValueError("Side must be 'B' for Buy or 'S' for Sell")

    if order_id < 0:
        raise ValueError("Order ID cannot be negative")

    if price <= 0:
        raise ValueError("Price must be greater than zero")

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")

    return ORDER_STRUCT.pack(
        order_id,
        side.encode("ascii"),
        price,
        quantity,
        timestamp,
    )


def unpack_order(data):
    """
    Convert a raw binary record back into order fields.
    """

    if len(data) != ORDER_SIZE:
        raise ValueError(
            f"Invalid order record size: expected {ORDER_SIZE}, got {len(data)}"
        )

    order_id, side, price, quantity, timestamp = ORDER_STRUCT.unpack(data)

    return {
        "order_id": order_id,
        "side": side.decode("ascii"),
        "price": price,
        "quantity": quantity,
        "timestamp": timestamp,
    }