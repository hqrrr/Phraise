# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for main shutdown.
"""Tests that HarperClient.shutdown_all is called exactly once during app shutdown.

Task 28: The duplicate ``HarperClient.shutdown_all()`` call has been removed
from ``_quit_app()``. Only the ``aboutToQuit`` connection in ``main()``
should trigger shutdown_all.

Verifies:
1. ``_quit_app`` does NOT call ``HarperClient.shutdown_all``.
2. ``main()`` sets up the ``aboutToQuit`` connection that calls it once.
"""

import unittest
from unittest.mock import MagicMock, patch


class TestQuitAppNoShutdown(unittest.TestCase):
    """``_quit_app`` must NOT call ``HarperClient.shutdown_all``."""

    def setUp(self):
        self.qapp_mock = MagicMock()
        self.qapp_patcher = patch("phraise.main.QApplication.instance",
                                  return_value=self.qapp_mock)
        self.addCleanup(self.qapp_patcher.stop)
        self.qapp_patcher.start()

        # Patch hotkey_manager so stop() is a no-op
        self.hk_patcher = patch("phraise.main.hotkey_manager")
        self.addCleanup(self.hk_patcher.stop)
        self.hk_patcher.start()

        # Patch write_error to silence logging
        self.we_patcher = patch("phraise.main.write_error")
        self.addCleanup(self.we_patcher.stop)
        self.we_patcher.start()

        from phraise.main import PhrAIseApp
        self.app = PhrAIseApp()

    def test_quit_app_does_not_import_harper_client(self):
        """After fix, _quit_app should not import HarperClient."""
        def _import_hook(name, *args, **kwargs):
            if "harper_client" in name:
                raise AssertionError(
                    "_quit_app should not import harper_client"
                )
            return __import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_import_hook):
            try:
                self.app._quit_app()
            except AssertionError as e:
                self.fail(str(e))

    def test_quit_app_does_not_call_shutdown_all(self):
        """_quit_app must not call HarperClient.shutdown_all."""
        with patch("phraise.harper_client.HarperClient.shutdown_all") as mock_sa:
            self.app._quit_app()
            mock_sa.assert_not_called()


class TestMainShutdownAllOnce(unittest.TestCase):
    """``main()`` must connect ``aboutToQuit`` to ``HarperClient.shutdown_all``."""

    def test_aboutToQuit_connected_to_shutdown_all(self):
        """Verify main() connects aboutToQuit to a lambda calling shutdown_all."""
        mock_app = MagicMock()
        mock_app.aboutToQuit = MagicMock()

        with patch("phraise.main.QApplication") as mock_qapp_cls:
            mock_qapp_cls.instance.return_value = mock_app
            mock_qapp_cls.return_value = mock_app

            with patch("phraise.main.config") as mock_config:
                mock_config.get.return_value = ""

                # Theme is handled by palette_for_theme + apply_theme — no _dark_palette
                with patch("phraise.dispatch.init"):
                    with patch("phraise.theme.DEFAULT_THEME", "dark"):
                        with patch("phraise.theme.generate_app_stylesheet",
                                   return_value=""):
                            with patch("phraise.main.PhrAIseApp"):
                                with patch(
                                    "phraise.harper_client.HarperClient"
                                ) as mock_hc:
                                    from phraise.main import main
                                    main()
                                    # The lambda wraps shutdown_all — invoke it
                                    (cb,) = mock_app.aboutToQuit.connect.\
                                        call_args[0]
                                    cb()
                                    mock_hc.shutdown_all.\
                                        assert_called_once()
