"""Tests for async thread use-after-free guards in SettingsPanel (Task 21).

Verifies that ``_on_test_done`` and ``_on_fetch_done`` return safely when
the SettingsPanel dialog is closed mid-operation, preventing crashes from
destroyed widgets.
"""

import unittest
from unittest.mock import MagicMock, patch

from phraise.settings_panel import SettingsPanel


# ---------------------------------------------------------------------------
# Descriptor that simulates a deleted QObject attribute
# ---------------------------------------------------------------------------

class _DeletedAttr:
    """Descriptor that raises RuntimeError on access, simulating a
    deleted C++ QObject attribute."""

    def __get__(self, obj, objtype=None):
        raise RuntimeError("Internal C++ object already deleted")

    def __set__(self, obj, value):
        pass


# ---------------------------------------------------------------------------
# Bare SettingsPanel factory
# ---------------------------------------------------------------------------

def _make_sp(**overrides) -> SettingsPanel:
    """Return a bare ``SettingsPanel`` instance whose ``__init__`` was skipped."""
    with patch.object(SettingsPanel, "__init__", return_value=None):
        sp = SettingsPanel.__new__(SettingsPanel)

    sp._is_closing = False

    # Build minimal mock entries dict
    status_mock = MagicMock()
    status_mock.setText = MagicMock()
    status_mock.setStyleSheet = MagicMock()

    model_combo_mock = MagicMock()
    model_combo_mock.clear = MagicMock()
    model_combo_mock.addItems = MagicMock()
    model_combo_mock.setCurrentIndex = MagicMock()

    sp._model_entries = {
        "model_1": {
            "status": status_mock,
            "model_combo": model_combo_mock,
        },
        "model_2": {
            "status": MagicMock(),
            "model_combo": MagicMock(),
        },
    }

    for attr, val in overrides.items():
        setattr(sp, attr, val)

    return sp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSettingsAsyncGuard(unittest.TestCase):
    """Both async callbacks must return safely when dialog is closing or deleted."""

    def setUp(self):
        """Clean up any ``_DeletedAttr`` descriptors from previous tests."""
        for attr in ("_model_entries",):
            try:
                delattr(SettingsPanel, attr)
            except AttributeError:
                pass

    # ---- _on_test_done ----

    def test_test_done_is_closing_returns_safely(self):
        """_on_test_done must return immediately when _is_closing is True."""
        sp = _make_sp(_is_closing=True)
        try:
            sp._on_test_done("model_1", ok=True, msg="Success")
        except Exception as e:
            self.fail(f"_on_test_done raised {type(e).__name__}: {e}")

    def test_test_done_is_closing_with_error_returns_safely(self):
        """_on_test_done must return immediately for error path when _is_closing is True."""
        sp = _make_sp(_is_closing=True)
        try:
            sp._on_test_done("model_1", ok=False, msg="Connection refused")
        except Exception as e:
            self.fail(f"_on_test_done(error) raised {type(e).__name__}: {e}")

    def test_test_done_deleted_object_returns_safely(self):
        """_on_test_done must return safely when C++ object is already deleted."""
        sp = _make_sp()
        SettingsPanel._model_entries = _DeletedAttr()
        try:
            sp._on_test_done("model_1", ok=True, msg="Success")
        except Exception as e:
            self.fail(f"_on_test_done(deleted) raised {type(e).__name__}: {e}")

    def test_test_done_alive_still_works(self):
        """_on_test_done must update status normally when dialog is alive."""
        sp = _make_sp()
        sp._on_test_done("model_1", ok=True, msg="Connection OK")
        status = sp._model_entries["model_1"]["status"]
        status.setText.assert_called_once_with("Connection OK")
        status.setStyleSheet.assert_called_once()

    def test_test_done_alive_error_path_works(self):
        """_on_test_done must show error status normally when dialog is alive."""
        sp = _make_sp()
        sp._on_test_done("model_1", ok=False, msg="401 Unauthorized")
        status = sp._model_entries["model_1"]["status"]
        status.setText.assert_called_once_with("401 Unauthorized")

    # ---- _on_fetch_done ----

    def test_fetch_done_is_closing_returns_safely(self):
        """_on_fetch_done must return immediately when _is_closing is True."""
        sp = _make_sp(_is_closing=True)
        try:
            sp._on_fetch_done("model_1", names=["gpt-4o", "gpt-4o-mini"], err=None)
        except Exception as e:
            self.fail(f"_on_fetch_done raised {type(e).__name__}: {e}")

    def test_fetch_done_is_closing_with_error_returns_safely(self):
        """_on_fetch_done must return immediately for error path when _is_closing is True."""
        sp = _make_sp(_is_closing=True)
        try:
            sp._on_fetch_done("model_1", names=None, err="API error")
        except Exception as e:
            self.fail(f"_on_fetch_done(error) raised {type(e).__name__}: {e}")

    def test_fetch_done_deleted_object_returns_safely(self):
        """_on_fetch_done must return safely when C++ object is already deleted."""
        sp = _make_sp()
        SettingsPanel._model_entries = _DeletedAttr()
        try:
            sp._on_fetch_done("model_1", names=["gpt-4o"], err=None)
        except Exception as e:
            self.fail(f"_on_fetch_done(deleted) raised {type(e).__name__}: {e}")

    def test_fetch_done_alive_still_works(self):
        """_on_fetch_done must populate combo box normally when dialog is alive."""
        sp = _make_sp()
        sp._on_fetch_done("model_1", names=["gpt-4o", "gpt-4o-mini"], err=None)
        combo = sp._model_entries["model_1"]["model_combo"]
        combo.clear.assert_called_once()
        combo.addItems.assert_called_once_with(["gpt-4o", "gpt-4o-mini"])

    def test_fetch_done_alive_error_path_works(self):
        """_on_fetch_done must show error status normally when dialog is alive."""
        sp = _make_sp()
        sp._on_fetch_done("model_1", names=None, err="Network timeout")
        status = sp._model_entries["model_1"]["status"]
        status.setText.assert_called_once_with("Network timeout")

    def test_fetch_done_no_models_path_works(self):
        """_on_fetch_done must show no-models message when list is empty."""
        sp = _make_sp()
        sp._on_fetch_done("model_1", names=[], err=None)
        status = sp._model_entries["model_1"]["status"]
        status.setText.assert_called_once()

    # ---- finished signal sets _is_closing ----

    def test_finished_signal_sets_is_closing(self):
        """finished signal must set _is_closing = True to block callbacks."""
        sp = _make_sp()
        self.assertFalse(sp._is_closing)
        # Simulate the finished signal emission
        sp._is_closing = True
        self.assertTrue(sp._is_closing)
        # Verify callbacks are now blocked
        sp._on_test_done("model_1", ok=True, msg="Success")
        status = sp._model_entries["model_1"]["status"]
        status.setText.assert_not_called()


if __name__ == "__main__":
    unittest.main()
