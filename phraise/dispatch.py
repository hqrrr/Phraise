# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Thread-safe dispatcher to the main Qt thread.
from PySide6.QtCore import QObject, Signal


class _Dispatcher(QObject):
    _call = Signal(object)

    def __init__(self):
        super().__init__()
        self._call.connect(self._run)

    def _run(self, fn):
        fn()


_dispatcher = None


def init():
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = _Dispatcher()


def run_on_main(fn):
    if _dispatcher is not None:
        _dispatcher._call.emit(fn)
    else:
        fn()
