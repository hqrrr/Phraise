import time
import threading
from collections.abc import Callable

from .config import config
from .error_log import write_error
from .text_grabber import TextGrabber


class Detector:
    """Window detection, whitelist/blacklist, and auto-trigger on pause or selection."""

    def __init__(self, on_trigger: Callable[[str, str], None]):
        self._on_trigger = on_trigger
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_text: str = ""
        self._grabber = TextGrabber()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _poll_loop(self):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            last_active_text = ""

            while self._running:
                try:
                    if not self._should_detect():
                        time.sleep(0.5)
                        last_active_text = ""
                        continue

                    auto_on_select = config.get("trigger", "auto_on_selection", default=True)

                    if auto_on_select:
                        selected = self._grabber.get_selected_text(use_clipboard=False)
                        if selected and len(selected.strip()) >= config.get("trigger", "min_chars_for_auto", default=20):
                            if selected != last_active_text:
                                last_active_text = selected
                                self._on_trigger(selected, "optimize")
                                time.sleep(1.0)
                                continue

                except Exception as e:
                    write_error(e, "_poll_loop")
                    pass

                time.sleep(0.5)
        finally:
            pythoncom.CoUninitialize()

    def _should_detect(self) -> bool:
        try:
            foreground = self._grabber.get_foreground_process_name()
            if not foreground:
                return True

            blacklist = config.get("blacklist", default=[])
            fg_lower = foreground.lower()

            for bl in blacklist:
                if bl.lower() in fg_lower or fg_lower == bl.lower():
                    return False

            return True
        except Exception as e:
            write_error(e, "_should_detect")
            return True


