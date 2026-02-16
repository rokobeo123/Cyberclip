"""Magazine paste - sequential clipboard injection (FIFO/LIFO)."""
from typing import List, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from cyberclip.storage.models import ClipboardItem


class Magazine(QObject):
    queue_changed = pyqtSignal(int, int)  # current_index, total
    queue_empty = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: List[ClipboardItem] = []
        self._index = 0
        self._mode = "FIFO"  # FIFO or LIFO

    def set_mode(self, mode: str):
        self._mode = mode

    def load(self, items: List[ClipboardItem]):
        if self._mode == "FIFO":
            self._queue = list(items)
        else:
            self._queue = list(reversed(items))
        self._index = 0
        self._emit_status()

    def add(self, item: ClipboardItem):
        if self._mode == "FIFO":
            self._queue.append(item)
        else:
            self._queue.insert(0, item)
        self._emit_status()

    def peek(self) -> Optional[ClipboardItem]:
        if self._index < len(self._queue):
            return self._queue[self._index]
        return None

    def fire(self) -> Optional[ClipboardItem]:
        """Get the next item and advance the pointer."""
        if self._index < len(self._queue):
            item = self._queue[self._index]
            self._index += 1
            self._emit_status()
            if self._index >= len(self._queue):
                self.queue_empty.emit()
            return item
        self.queue_empty.emit()
        return None

    def reset(self):
        self._index = 0
        self._emit_status()

    def clear(self):
        self._queue.clear()
        self._index = 0
        self._emit_status()

    def set_start(self, item_id: int):
        """Set magazine pointer to the item with the given ID."""
        for i, item in enumerate(self._queue):
            if item.id == item_id:
                self._index = i
                self._emit_status()
                return True
        return False

    def reorder(self, item_ids: List[int]):
        """Reorder the queue to match the given list of item IDs.
        Items not in item_ids are appended at the end.
        Preserves the current pointer's target item when possible."""
        current_item = self.peek()
        id_to_item = {it.id: it for it in self._queue}
        new_queue = []
        for iid in item_ids:
            if iid in id_to_item:
                new_queue.append(id_to_item.pop(iid))
        # Append any remaining items not in the new order
        for it in self._queue:
            if it.id in id_to_item:
                new_queue.append(it)
                del id_to_item[it.id]
        self._queue = new_queue
        # Restore pointer to the same item if possible
        if current_item:
            for i, it in enumerate(self._queue):
                if it.id == current_item.id:
                    self._index = i
                    break
        self._emit_status()

    @property
    def remaining(self) -> int:
        return max(0, len(self._queue) - self._index)

    @property
    def total(self) -> int:
        return len(self._queue)

    @property
    def current_index(self) -> int:
        return self._index

    def _emit_status(self):
        self.queue_changed.emit(self._index, len(self._queue))
