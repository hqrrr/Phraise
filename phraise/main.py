import os
import sys
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from .config import config
from .dispatch import run_on_main
from .error_log import write_error
from .floating_ball import FloatingBall
from .floating_window import FloatingWindow
from .hotkeys import hotkey_manager
from .text_grabber import TextGrabber


class PhrAIseApp:
    """Main application class that ties together all modules."""

    def __init__(self):
        self._ball: FloatingBall | None = None
        self._window: FloatingWindow | None = None
        self._tray: QSystemTrayIcon | None = None
        self._grabber = TextGrabber()
        self._running = True

    def run(self):
        self._init_ball()
        self._init_tray()
        self._init_hotkeys()
        QApplication.instance().exec()

    def _init_ball(self):
        self._ball = FloatingBall(
            on_click=self._expand_window,
            on_right_click=self._ball_right_click,
        )
        self._ball.show()
        start_minimized = config.get("general", "start_minimized", default=False)
        if start_minimized:
            self._ball.hide()

    def _init_tray(self):
        self._tray = QSystemTrayIcon()
        self._tray.setIcon(self._create_tray_icon())
        self._tray.setToolTip("PhrAIse")

        menu = QMenu()
        menu.addAction("显示悬浮球", self._toggle_ball)
        menu.addSeparator()
        menu.addAction("设置...", self._show_settings)
        menu.addSeparator()
        menu.addAction("退出 PhrAIse", self._quit_app)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._toggle_ball()

    def _init_hotkeys(self):
        hotkey_manager.register("trigger", self._hotkey_trigger)
        hotkey_manager.register("toggle_ball", self._toggle_ball)
        hotkey_manager.start()

    def _expand_window(self, text: str | None = None, mode: str = "optimize"):
        if self._window is None:
            try:
                self._window = FloatingWindow(
                    on_close=self._on_window_close,
                )
            except Exception as e:
                write_error(e, "_expand_window:create")
                return

        if text:
            self._window.load_text(text, mode)
        else:
            self._window.deiconify()
            self._window.lift()
            QTimer.singleShot(50, self._window.focus_force)

    def _on_window_close(self):
        if self._ball:
            self._ball.show()

    def _ball_right_click(self, event):
        menu = QMenu()
        if self._ball.isVisible():
            menu.addAction("隐藏悬浮球", self._ball.hide)
        else:
            menu.addAction("显示悬浮球", self._ball.show)
        menu.addAction("设置...", self._show_settings)
        menu.addSeparator()
        menu.addAction("退出", self._quit_app)
        menu.exec(event.globalPosition().toPoint())

    def _toggle_ball(self):
        if self._ball:
            self._ball.toggle()

    def _show_settings(self):
        QTimer.singleShot(0, self._open_settings)

    def _open_settings(self):
        from .settings_panel import SettingsPanel
        parent = self._window if self._window else None
        dlg = SettingsPanel(parent)
        dlg.exec()

    def _hotkey_trigger(self):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            selected = self._grabber.get_selected_text()
            run_on_main(lambda: self._on_trigger_dispatch(selected))
        except Exception as e:
            write_error(e, "_hotkey_trigger")
        finally:
            pythoncom.CoUninitialize()

    def _on_trigger_dispatch(self, selected: str):
        self._grabber.capture_foreground()
        window_open = self._window is not None and self._window.isVisible()
        if window_open:
            mode = self._window._current_mode
        else:
            mode = "optimize"

        if selected:
            self._expand_window(selected, mode)
        else:
            if not window_open and self._ball and not self._ball.isVisible():
                self._ball.show()
            self._expand_window(mode=mode)

    def _quit_app(self):
        self._running = False
        hotkey_manager.stop()
        try:
            if self._window:
                self._window.hide()
        except Exception as e:
            write_error(e, "_quit_app:hide_window")
            pass
        try:
            if self._ball:
                self._ball.hide()
        except Exception as e:
            write_error(e, "_quit_app:hide_ball")
            pass
        try:
            if self._tray:
                self._tray.hide()
        except Exception as e:
            write_error(e, "_quit_app:hide_tray")
            pass
        QApplication.instance().quit()

    @staticmethod
    def _create_tray_icon() -> QIcon:
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#6c5ce7"), 3))
        p.setBrush(QBrush(QColor("#2b2b2b")))
        p.drawEllipse(4, 4, size - 8, size - 8)
        font = QFont("Segoe UI", 18, QFont.Bold)
        p.setFont(font)
        p.setPen(QColor("white"))
        p.drawText(pixmap.rect(), Qt.AlignCenter, "AI")
        p.end()
        return QIcon(pixmap)


def main():
    import multiprocessing
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    from .dispatch import init as init_dispatch
    init_dispatch()

    app.setStyle("Fusion")
    app.setPalette(_dark_palette())

    phr_app = PhrAIseApp()
    phr_app.run()


def _dark_palette():
    from PySide6.QtGui import QPalette
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#1e1e2e"))
    p.setColor(QPalette.WindowText, QColor("#cdd6f4"))
    p.setColor(QPalette.Base, QColor("#313244"))
    p.setColor(QPalette.AlternateBase, QColor("#1e1e2e"))
    p.setColor(QPalette.ToolTipBase, QColor("#313244"))
    p.setColor(QPalette.ToolTipText, QColor("#cdd6f4"))
    p.setColor(QPalette.Text, QColor("#cdd6f4"))
    p.setColor(QPalette.Button, QColor("#313244"))
    p.setColor(QPalette.ButtonText, QColor("#cdd6f4"))
    p.setColor(QPalette.BrightText, Qt.red)
    p.setColor(QPalette.Highlight, QColor("#6c5ce7"))
    p.setColor(QPalette.HighlightedText, QColor("white"))
    return p


if __name__ == "__main__":
    main()
