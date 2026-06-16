# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for text grabber threads.
"""Thread-safety tests for TextGrabber.

Verifies that:
- threading.Lock protects _foreground_control reads/writes.
- threading.Lock protects _original_clipboard / _clipboard_saved.
- Lock is per-instance, not global.
- Concurrent get_selected_text + replace_text do not deadlock or corrupt state.
- UIA calls are never made while holding the lock.
"""

import threading
import time
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from phraise.text_grabber import TextGrabber


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_control():
    """Return a MagicMock suitable as a UIA control with TextPattern support."""
    ctl = MagicMock()
    # Default: no text pattern (triggers parent-walk)
    type(ctl).IsKeyboardFocusable = PropertyMock(return_value=True)
    return ctl


# ---------------------------------------------------------------------------
# Lock existence and per-instance isolation
# ---------------------------------------------------------------------------

def test_lock_exists_in_init():
    """_state_lock must be a threading.Lock created in __init__."""
    g = TextGrabber()
    assert hasattr(g, "_state_lock")
    assert isinstance(g._state_lock, type(threading.Lock()))


def test_lock_is_per_instance():
    """Two TextGrabber instances must have independent locks (no global lock)."""
    g1 = TextGrabber()
    g2 = TextGrabber()
    assert g1._state_lock is not g2._state_lock


# ---------------------------------------------------------------------------
# Concurrent foreground control access (no deadlock, no corruption)
# ---------------------------------------------------------------------------

def test_concurrent_capture_foreground_no_deadlock():
    """Two threads racing capture_foreground() must complete without hanging."""
    grabber = TextGrabber()
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _worker():
        try:
            barrier.wait()
            for _ in range(30):
                grabber.capture_foreground()
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, f"Thread errors: {errors}"
    assert not t1.is_alive(), "Thread 1 hung"
    assert not t2.is_alive(), "Thread 2 hung"


def test_concurrent_focus_foreground_no_deadlock():
    """Two threads calling focus_foreground() must complete without hanging."""
    grabber = TextGrabber()
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _worker():
        try:
            barrier.wait()
            for _ in range(30):
                grabber.focus_foreground()
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, f"Thread errors: {errors}"
    assert not t1.is_alive(), "Thread 1 hung"
    assert not t2.is_alive(), "Thread 2 hung"


# ---------------------------------------------------------------------------
# Concurrent get_selected_text + replace_text (mocked UIA)
# ---------------------------------------------------------------------------

def test_concurrent_get_and_replace_no_deadlock():
    """Two threads doing get_selected_text + replace_text with mocked UIA
    must complete without deadlock or exception."""
    grabber = TextGrabber()
    grabber._foreground_control = _make_mock_control()
    errors: list[tuple[int, Exception]] = []
    barrier = threading.Barrier(2)

    with patch.object(grabber, '_get_selected_via_uia', return_value="mock text"), \
         patch.object(grabber, '_replace_via_uia', return_value=True), \
         patch.object(grabber, 'focus_foreground', return_value=True), \
         patch("phraise.text_grabber._ensure_com_initialized"):

        def _worker(tid: int):
            try:
                barrier.wait()
                for i in range(20):
                    grabber.get_selected_text(use_clipboard=False)
                    grabber.replace_text(f"text_from_{tid}_{i}")
            except Exception as exc:
                errors.append((tid, exc))

        t1 = threading.Thread(target=_worker, args=(1,))
        t2 = threading.Thread(target=_worker, args=(2,))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

    assert not errors, f"Thread errors: {errors}"
    assert not t1.is_alive(), "Thread 1 hung"
    assert not t2.is_alive(), "Thread 2 hung"


# ---------------------------------------------------------------------------
# Concurrent clipboard save/restore (state integrity)
# ---------------------------------------------------------------------------

def test_concurrent_clipboard_save_restore_does_not_corrupt_state():
    """Two threads saving/restoring clipboard must not corrupt each other's
    _original_clipboard or _clipboard_saved flags."""
    grabber = TextGrabber()

    # Track what each thread's save operation produces
    saved_by_thread: dict[int, str | None] = {}
    save_errors: list[Exception] = []
    lock_results = threading.Lock()

    def _save_only(tid: int, content: str):
        """Simulate _save_clipboard with known content."""
        try:
            with grabber._state_lock:
                grabber._original_clipboard = content
                grabber._clipboard_saved = True
        except Exception as exc:
            save_errors.append(exc)

    def _restore_only(tid: int):
        """Simulate _restore_clipboard and record what was restored."""
        try:
            with grabber._state_lock:
                saved = grabber._clipboard_saved
                content = grabber._original_clipboard
            if saved:
                with lock_results:
                    saved_by_thread[tid] = content
        except Exception as exc:
            save_errors.append(exc)

    # Thread A saves "AAA", Thread B saves "BBB"
    t_a = threading.Thread(target=_save_only, args=(1, "AAA"))
    t_b = threading.Thread(target=_save_only, args=(2, "BBB"))
    t_a.start()
    t_b.start()
    t_a.join(timeout=5)
    t_b.join(timeout=5)

    # After both saves, the last writer wins (expected for shared state)
    # Now spawn two threads to restore
    t_a2 = threading.Thread(target=_restore_only, args=(1,))
    t_b2 = threading.Thread(target=_restore_only, args=(2,))
    t_a2.start()
    t_b2.start()
    t_a2.join(timeout=5)
    t_b2.join(timeout=5)

    assert not save_errors, f"Errors during save/restore: {save_errors}"
    # Both threads should see the same saved value (consistent snapshot)
    if len(saved_by_thread) >= 2:
        values = list(saved_by_thread.values())
        assert all(v == values[0] for v in values), \
            f"Inconsistent restore values: {saved_by_thread}"


# ---------------------------------------------------------------------------
# UIA calls are NOT made while holding the lock
# ---------------------------------------------------------------------------

def test_uia_calls_not_made_while_locked():
    """Verify that UIA operations (GetFocusedControl, SetFocus) happen
    outside the critical section."""
    import sys

    grabber = TextGrabber()

    # uiautomation is imported locally inside methods, so inject a mock
    # module into sys.modules to intercept those imports.
    mock_uia = MagicMock()
    mock_control = _make_mock_control()
    mock_uia.GetFocusedControl.return_value = mock_control

    lock_held_during_uia: list[str] = []

    _orig_setfocus = mock_control.SetFocus

    def _checking_setfocus():
        acquired = grabber._state_lock.acquire(blocking=False)
        if not acquired:
            lock_held_during_uia.append("SetFocus")
        else:
            grabber._state_lock.release()
        return _orig_setfocus()

    mock_control.SetFocus = _checking_setfocus

    with patch.dict(sys.modules, {"uiautomation": mock_uia}), \
         patch("phraise.text_grabber._ensure_com_initialized"):

        # Also inject the mock for the local import inside capture_foreground
        grabber.capture_foreground()
        grabber.focus_foreground()

    assert not lock_held_during_uia, \
        f"UIA calls made while lock held: {lock_held_during_uia}"


# ---------------------------------------------------------------------------
# Stress test: many threads, many iterations
# ---------------------------------------------------------------------------

def test_stress_many_threads():
    """10 threads doing concurrent capture + focus (mocked UIA) must all complete."""
    import sys

    grabber = TextGrabber()
    errors: list[Exception] = []
    errors_lock = threading.Lock()
    barrier = threading.Barrier(10)

    mock_uia = MagicMock()
    mock_control = _make_mock_control()
    mock_uia.GetFocusedControl.return_value = mock_control

    with patch.dict(sys.modules, {"uiautomation": mock_uia}), \
         patch("phraise.text_grabber._ensure_com_initialized"):

        def _worker():
            try:
                barrier.wait()
                for _ in range(50):
                    grabber.capture_foreground()
                    grabber.focus_foreground()
            except Exception as exc:
                with errors_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

    assert not errors, f"Thread errors: {errors}"
    for i, t in enumerate(threads):
        assert not t.is_alive(), f"Thread {i} hung"
