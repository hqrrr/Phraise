# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for main init resilience.
"""Tests for main.py init resilience — individual _init_* failures must not crash run().

Task 28: Each ``_init_ball``, ``_init_tray``, ``_init_hotkeys`` call in
``PhrAIseApp.run()`` is wrapped in its own try/except so that a failure in
one does not prevent subsequent initialisations.

Also verifies that ``_hotkey_trigger`` does not crash when ``pythoncom``
is unavailable (import error).
"""

import unittest
from unittest.mock import MagicMock, patch

from phraise.main import PhrAIseApp


class TestPhrAIseAppInitResilience(unittest.TestCase):
    """Each init failure must be caught independently."""

    def setUp(self):
        # Patch QApplication.instance for exec()
        self.qapp_mock = MagicMock()
        qapp_patcher = patch(
            "phraise.main.QApplication.instance", return_value=self.qapp_mock
        )
        self.addCleanup(qapp_patcher.stop)
        qapp_patcher.start()

        # Patch _init_* methods to allow per-test override
        self._init_ball_patcher = patch.object(PhrAIseApp, "_init_ball")
        self._init_tray_patcher = patch.object(PhrAIseApp, "_init_tray")
        self._init_hotkeys_patcher = patch.object(PhrAIseApp, "_init_hotkeys")
        self.mock_init_ball = self._init_ball_patcher.start()
        self.mock_init_tray = self._init_tray_patcher.start()
        self.mock_init_hotkeys = self._init_hotkeys_patcher.start()
        self.addCleanup(self._init_ball_patcher.stop)
        self.addCleanup(self._init_tray_patcher.stop)
        self.addCleanup(self._init_hotkeys_patcher.stop)

        # Patch write_error to track errors without side effects
        self.werror_patcher = patch("phraise.main.write_error")
        self.mock_write_error = self.werror_patcher.start()
        self.addCleanup(self.werror_patcher.stop)

        self.app = PhrAIseApp()

    def test_all_inits_succeed(self):
        """Normal path: all _init_* are called and exec() runs."""
        self.app.run()
        self.mock_init_ball.assert_called_once()
        self.mock_init_tray.assert_called_once()
        self.mock_init_hotkeys.assert_called_once()
        self.qapp_mock.exec.assert_called_once()
        self.mock_write_error.assert_not_called()

    def test_ball_init_fails_others_still_run(self):
        """If _init_ball raises, _init_tray and _init_hotkeys still run."""
        self.mock_init_ball.side_effect = RuntimeError("ball crashed")
        self.app.run()
        self.mock_init_tray.assert_called_once()
        self.mock_init_hotkeys.assert_called_once()
        self.qapp_mock.exec.assert_called_once()
        self.mock_write_error.assert_called_once()

    def test_tray_init_fails_others_still_run(self):
        """If _init_tray raises, _init_hotkeys still runs."""
        self.mock_init_tray.side_effect = RuntimeError("tray crashed")
        self.app.run()
        self.mock_init_ball.assert_called_once()
        self.mock_init_hotkeys.assert_called_once()
        self.qapp_mock.exec.assert_called_once()
        self.assertEqual(self.mock_write_error.call_count, 1)

    def test_hotkeys_init_fails_others_still_run(self):
        """If _init_hotkeys raises, _init_ball and _init_tray still run."""
        self.mock_init_hotkeys.side_effect = RuntimeError("hotkeys crashed")
        self.app.run()
        self.mock_init_ball.assert_called_once()
        self.mock_init_tray.assert_called_once()
        self.qapp_mock.exec.assert_called_once()
        self.assertEqual(self.mock_write_error.call_count, 1)

    def test_all_inits_fail_still_reaches_exec(self):
        """Even when every _init_* raises, run() must still reach exec()."""
        self.mock_init_ball.side_effect = RuntimeError("ball fail")
        self.mock_init_tray.side_effect = RuntimeError("tray fail")
        self.mock_init_hotkeys.side_effect = RuntimeError("hotkeys fail")
        self.app.run()
        self.qapp_mock.exec.assert_called_once()
        self.assertEqual(self.mock_write_error.call_count, 3)

    def test_write_error_context_labels(self):
        """Error labels must include the 'run:' prefix for each init."""
        self.mock_init_ball.side_effect = ValueError("bad ball")
        self.mock_init_tray.side_effect = TypeError("bad tray")
        self.app.run()
        labels = [c.args[1] for c in self.mock_write_error.call_args_list]
        self.assertIn("run:_init_ball", labels)
        self.assertIn("run:_init_tray", labels)

    def test_hotkey_trigger_import_error_does_not_crash(self):
        """_hotkey_trigger must not crash when pythoncom import fails."""
        # Un-patch _init_hotkeys so the real method runs
        self._init_hotkeys_patcher.stop()
        # Patch the import inside _hotkey_trigger
        with patch("builtins.__import__") as mock_import:
            mock_import.side_effect = ImportError("No module named pythoncom")
            try:
                self.app._hotkey_trigger()
            except Exception as e:
                self.fail(f"_hotkey_trigger raised {type(e).__name__}: {e}")
        self._init_hotkeys_patcher.start()


class TestHotkeyTriggerImportError(unittest.TestCase):
    """Direct tests for _hotkey_trigger import error handling."""

    def setUp(self):
        self.app = PhrAIseApp()
        self.app._grabber = MagicMock()
        # Prevent _on_trigger_dispatch from running (it needs Qt)
        self.app._on_trigger_dispatch = MagicMock()

    def test_pythoncom_import_failure_logged(self):
        """ImportError on pythoncom is caught and logged via write_error."""
        with patch("phraise.main.write_error") as mock_we:
            with patch("builtins.__import__") as mock_import:
                mock_import.side_effect = ImportError("No module named pythoncom")

                self.app._hotkey_trigger()

                mock_we.assert_called_once()
                args, _ = mock_we.call_args
                self.assertIsInstance(args[0], ImportError)
                self.assertEqual(args[1], "_hotkey_trigger")

    def test_pythoncom_import_failure_coinitialize_not_called(self):
        """When pythoncom import fails, CoInitialize must not be called."""
        with patch("phraise.main.write_error"):
            with patch("builtins.__import__") as mock_import:
                mock_import.side_effect = ImportError("No module named pythoncom")

                # Also patch the text grabber to verify it's NOT called
                self.app._grabber.get_selected_text = MagicMock()

                self.app._hotkey_trigger()

                self.app._grabber.get_selected_text.assert_not_called()
