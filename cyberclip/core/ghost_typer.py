"""Ghost Typer - simulates keyboard typing character by character."""
import time
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QMutex


class GhostTypeWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int, int)  # current_char, total

    def __init__(self, text: str, delay_ms: int = 15):
        super().__init__()
        self.text = text
        self.delay_ms = delay_ms
        self._abort = False
        self._mutex = QMutex()

    def abort(self):
        self._mutex.lock()
        self._abort = True
        self._mutex.unlock()

    def run(self):
        from cyberclip.utils.win32_helpers import send_unicode_char, send_key, VK_RETURN
        total = len(self.text)
        for i, ch in enumerate(self.text):
            self._mutex.lock()
            aborted = self._abort
            self._mutex.unlock()
            if aborted:
                break

            if ch == '\n':
                send_key(vk=VK_RETURN)
                send_key(vk=VK_RETURN, flags=0x0002)  # KEYEVENTF_KEYUP
            else:
                send_unicode_char(ch)

            self.progress.emit(i + 1, total)
            time.sleep(self.delay_ms / 1000.0)

        self.finished.emit()


class GhostTyper(QObject):
    typing_started = pyqtSignal()
    typing_finished = pyqtSignal()
    typing_progress = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None

    def type_text(self, text: str, delay_ms: int = 15):
        if self._thread and self._thread.isRunning():
            return

        self._thread = QThread()
        self._worker = GhostTypeWorker(text, delay_ms)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._on_finished)
        self._worker.progress.connect(self.typing_progress.emit)

        self.typing_started.emit()
        self._thread.start()

    def abort(self):
        if self._worker:
            self._worker.abort()

    def _on_finished(self):
        self.typing_finished.emit()
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None

    @property
    def is_typing(self) -> bool:
        return self._thread is not None and self._thread.isRunning()
