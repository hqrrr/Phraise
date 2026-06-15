"""Shared PySide6 QApplication fixture for all tests.

Provides a lazily-initialized QApplication singleton via the ``qapp``
pytest fixture, matching the existing pattern used in
``TestThemeComboSelection.setUpClass`` and similar test classes.

Optional ``qtbot`` fixture is only registered when ``pytestqt`` is
installed (graceful fallback, not a hard dependency).
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Module-level singleton -- lazily initialized on first access
# ---------------------------------------------------------------------------
_qapp: QApplication | None = None


def _get_qapp() -> QApplication:
    """Return the module-level QApplication singleton, creating it if needed."""
    global _qapp
    if _qapp is None:
        _qapp = QApplication.instance()
        if _qapp is None:
            _qapp = QApplication([])
    return _qapp


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """Return the shared QApplication singleton for this test session."""
    return _get_qapp()


# ---------------------------------------------------------------------------
# Optional ``qtbot`` fixture  --  only when pytest-qt is installed
# ---------------------------------------------------------------------------
try:
    from pytestqt.qtbot import QtBot as _QtBot

    _HAS_PYTEST_QT = True
except ImportError:
    _HAS_PYTEST_QT = False


@pytest.fixture()
def qtbot(qapp):
    """Provide a ``qtbot`` fixture for Qt test helpers.

    Requires ``pytest-qt`` -- if not installed the test is skipped
    gracefully instead of crashing on import.
    """
    if not _HAS_PYTEST_QT:
        pytest.skip("pytest-qt is not installed")
    return _QtBot(qapp)
