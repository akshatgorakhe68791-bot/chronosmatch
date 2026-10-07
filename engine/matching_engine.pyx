# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from libc.stdint cimport uint64_t


cdef struct COrder:
    uint64_t order_id
    char side
    double price
    unsigned int quantity
    uint64_t sequence


cdef struct CTrade:
    uint64_t buy_order_id
    uint64_t sell_order_id
    double price
    unsigned int quantity


cdef class MatchingEngine:

    cdef COrder bids[10000]
    cdef COrder asks[10000]

    cdef int bid_count
    cdef int ask_count

    cdef uint64_t sequence
    cdef uint64_t total_orders
    cdef uint64_t total_trades

    def __cinit__(self):
        self.bid_count = 0
        self.ask_count = 0
        self.sequence = 0
        self.total_orders = 0
        self.total_trades = 0

    cdef int best_bid_index(self):
        cdef int i
        cdef int best

        if self.bid_count == 0:
            return -1

        best = 0

        for i in range(1, self.bid_count):

            if self.bids[i].price > self.bids[best].price:
                best = i

            elif (
                self.bids[i].price == self.bids[best].price
                and self.bids[i].sequence < self.bids[best].sequence
            ):
                best = i

        return best

    cdef int best_ask_index(self):
        cdef int i
        cdef int best

        if self.ask_count == 0:
            return -1

        best = 0

        for i in range(1, self.ask_count):

            if self.asks[i].price < self.asks[best].price:
                best = i

            elif (
                self.asks[i].price == self.asks[best].price
                and self.asks[i].sequence < self.asks[best].sequence
            ):
                best = i

        return best

    cdef void remove_bid(self, int index):
        cdef int i

        for i in range(index, self.bid_count - 1):
            self.bids[i] = self.bids[i + 1]

        self.bid_count -= 1

    cdef void remove_ask(self, int index):
        cdef int i

        for i in range(index, self.ask_count - 1):
            self.asks[i] = self.asks[i + 1]

        self.ask_count -= 1

    cpdef list add_order(
        self,
        uint64_t order_id,
        str side,
        double price,
        unsigned int quantity,
    ):
        cdef COrder incoming
        cdef int index
        cdef unsigned int trade_quantity
        cdef double trade_price
        cdef list trades = []

        if side != "B" and side != "S":
            raise ValueError("Side must be B or S")

        if price <= 0:
            raise ValueError("Price must be greater than zero")

        if quantity == 0:
            raise ValueError("Quantity must be greater than zero")

        self.sequence += 1
        self.total_orders += 1

        incoming.order_id = order_id
        incoming.side = 66 if side == "B" else 83
        incoming.price = price
        incoming.quantity = quantity
        incoming.sequence = self.sequence

        # -------------------------------------------------
        # BUY ORDER
        # -------------------------------------------------

        if incoming.side == 66:

            while incoming.quantity > 0 and self.ask_count > 0:

                index = self.best_ask_index()

                if self.asks[index].price > incoming.price:
                    break

                if incoming.quantity < self.asks[index].quantity:
                    trade_quantity = incoming.quantity
                else:
                    trade_quantity = self.asks[index].quantity

                # Resting order determines execution price.
                trade_price = self.asks[index].price

                trades.append({
                    "buy_order_id": incoming.order_id,
                    "sell_order_id": self.asks[index].order_id,
                    "price": trade_price,
                    "quantity": trade_quantity,
                })

                self.total_trades += 1

                incoming.quantity -= trade_quantity
                self.asks[index].quantity -= trade_quantity

                if self.asks[index].quantity == 0:
                    self.remove_ask(index)

            if incoming.quantity > 0:

                if self.bid_count >= 10000:
                    raise OverflowError("Bid book capacity exceeded")

                self.bids[self.bid_count] = incoming
                self.bid_count += 1

        # -------------------------------------------------
        # SELL ORDER
        # -------------------------------------------------

        else:

            while incoming.quantity > 0 and self.bid_count > 0:

                index = self.best_bid_index()

                if self.bids[index].price < incoming.price:
                    break

                if incoming.quantity < self.bids[index].quantity:
                    trade_quantity = incoming.quantity
                else:
                    trade_quantity = self.bids[index].quantity

                trade_price = self.bids[index].price

                trades.append({
                    "buy_order_id": self.bids[index].order_id,
                    "sell_order_id": incoming.order_id,
                    "price": trade_price,
                    "quantity": trade_quantity,
                })

                self.total_trades += 1

                incoming.quantity -= trade_quantity
                self.bids[index].quantity -= trade_quantity

                if self.bids[index].quantity == 0:
                    self.remove_bid(index)

            if incoming.quantity > 0:

                if self.ask_count >= 10000:
                    raise OverflowError("Ask book capacity exceeded")

                self.asks[self.ask_count] = incoming
                self.ask_count += 1

        return trades

    cpdef object best_bid(self):

        cdef int index = self.best_bid_index()

        if index == -1:
            return None

        return {
            "order_id": self.bids[index].order_id,
            "price": self.bids[index].price,
            "quantity": self.bids[index].quantity,
        }

    cpdef object best_ask(self):

        cdef int index = self.best_ask_index()

        if index == -1:
            return None

        return {
            "order_id": self.asks[index].order_id,
            "price": self.asks[index].price,
            "quantity": self.asks[index].quantity,
        }

    cpdef dict stats(self):

        return {
            "orders": self.total_orders,
            "trades": self.total_trades,
            "bids": self.bid_count,
            "asks": self.ask_count,
        }