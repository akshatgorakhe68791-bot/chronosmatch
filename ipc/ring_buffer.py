
import mmap
import os
import struct
from pathlib import Path
from contextlib import nullcontext

from ipc.layout import ORDER_SIZE, pack_order, unpack_order

HEADER_STRUCT = struct.Struct("<QQ")
HEADER_SIZE = HEADER_STRUCT.size

DEFAULT_CAPACITY = 1024


class MMapRingBuffer:

    def __init__(
        self,
        path="chronosmatch_ring.dat",
        capacity=DEFAULT_CAPACITY,
        create=False,
        lock=None,
    ):
        self.path = Path(path)
        self.capacity = capacity
        self.lock = lock
        self.total_size = HEADER_SIZE + capacity * ORDER_SIZE

        if create:
            self._create_buffer()

        if not self.path.exists():
            raise FileNotFoundError(self.path)

        self.file = open(self.path, "r+b", buffering=0)

        actual_size = os.path.getsize(self.path)

        if actual_size != self.total_size:
            self.file.close()
            raise ValueError(
                f"Expected {self.total_size} bytes, "
                f"found {actual_size} bytes"
            )

        self.mm = mmap.mmap(
            self.file.fileno(),
            self.total_size,
            access=mmap.ACCESS_WRITE,
        )

    def _create_buffer(self):
        with open(self.path, "w+b") as file:
            file.truncate(self.total_size)
            file.seek(0)
            file.write(HEADER_STRUCT.pack(0, 0))

    def _get_write_index(self):
        return struct.unpack_from("<Q", self.mm, 0)[0]

    def _get_read_index(self):
        return struct.unpack_from("<Q", self.mm, 8)[0]

    def _set_write_index(self, value):
        struct.pack_into("<Q", self.mm, 0, value)

    def _set_read_index(self, value):
        struct.pack_into("<Q", self.mm, 8, value)

    def is_empty(self):
        with (self.lock if self.lock is not None else nullcontext()):
            return self._get_write_index() == self._get_read_index()

    def is_full(self):
        with (self.lock if self.lock is not None else nullcontext()):
            return (
                self._get_write_index() - self._get_read_index()
            ) >= self.capacity

    def size(self):
        with (self.lock if self.lock is not None else nullcontext()):
            return self._get_write_index() - self._get_read_index()

    def write_order(
        self,
        order_id,
        side,
        price,
        quantity,
        timestamp,
    ):
        with (self.lock if self.lock is not None else nullcontext()):
            write_index = self._get_write_index()
            read_index = self._get_read_index()

            if write_index - read_index >= self.capacity:
                return False

            slot = write_index % self.capacity
            offset = HEADER_SIZE + slot * ORDER_SIZE

            order_data = pack_order(
                order_id,
                side,
                price,
                quantity,
                timestamp,
            )

            self.mm[offset:offset + ORDER_SIZE] = order_data
            self._set_write_index(write_index + 1)

            return True

    def read_order(self):
        with (self.lock if self.lock is not None else nullcontext()):
            write_index = self._get_write_index()
            read_index = self._get_read_index()

            if write_index == read_index:
                return None

            slot = read_index % self.capacity
            offset = HEADER_SIZE + slot * ORDER_SIZE

            order_data = self.mm[offset:offset + ORDER_SIZE]
            order = unpack_order(order_data)

            self._set_read_index(read_index + 1)

            return order

    def close(self):
        if hasattr(self, "mm"):
            self.mm.flush()
            self.mm.close()

        if hasattr(self, "file"):
            self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
