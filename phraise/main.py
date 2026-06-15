import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPalette, QPen, QBrush, QFont, QPixmap, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from .config import config
from .i18n import t, add_listener, remove_listener
from .dispatch import run_on_main
from .error_log import write_error
from .floating_ball import FloatingBall
from .floating_window import FloatingWindow
from .hotkeys import hotkey_manager
from .text_grabber import TextGrabber
from .theme import (
    apply_theme,
    get_theme,
    generate_app_stylesheet,
    resolve_theme_name,
    theme_notifier,
    FullTheme,
)


class PhrAIseApp:
    """Main application class that ties together all modules."""

    def __init__(self):
        self._ball: FloatingBall | None = None
        self._window: FloatingWindow | None = None
        self._tray: QSystemTrayIcon | None = None
        self._grabber = TextGrabber()
        self._running = True

    def run(self):
        try:
            self._init_ball()
        except Exception as e:
            write_error(e, "run:_init_ball")
        try:
            self._init_tray()
        except Exception as e:
            write_error(e, "run:_init_tray")
        try:
            self._init_hotkeys()
        except Exception as e:
            write_error(e, "run:_init_hotkeys")
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
        menu.addAction(t("app.tray.show_ball"), self._toggle_ball)
        menu.addSeparator()
        menu.addAction(t("app.tray.settings"), self._show_settings)
        menu.addSeparator()
        menu.addAction(t("app.tray.quit"), self._quit_app)
        self._tray.setContextMenu(menu)
        self._tray_menu = menu
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()
        add_listener(self._rebuild_menus)
        theme_notifier.theme_changed.connect(self._update_tray_icon)

    def _update_tray_icon(self, _name: str):
        if self._tray:
            self._tray.setIcon(self._create_tray_icon())

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
                    grabber=self._grabber,
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
            menu.addAction(t("app.tray.hide_ball"), self._ball.hide)
        else:
            menu.addAction(t("app.tray.show_ball"), self._ball.show)
        menu.addAction(t("app.tray.settings"), self._show_settings)
        menu.addSeparator()
        menu.addAction(t("app.tray.quit_short"), self._quit_app)
        menu.exec(event.globalPosition().toPoint())

    def _rebuild_menus(self):
        if self._tray:
            menu = QMenu()
            menu.addAction(t("app.tray.show_ball"), self._toggle_ball)
            menu.addSeparator()
            menu.addAction(t("app.tray.settings"), self._show_settings)
            menu.addSeparator()
            menu.addAction(t("app.tray.quit"), self._quit_app)
            self._tray.setContextMenu(menu)
            self._tray_menu = menu

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
        try:
            import pythoncom
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            selected = self._grabber.get_selected_text()
            run_on_main(lambda: self._on_trigger_dispatch(selected))
        except Exception as e:
            write_error(e, "_hotkey_trigger")
        finally:
            try:
                pythoncom.CoUninitialize()
            except NameError:
                pass

    def _on_trigger_dispatch(self, selected: str):
        self._grabber.capture_foreground()
        window_open = self._window is not None and self._window.isVisible()
        if window_open:
            mode = self._window.current_mode
        else:
            mode = "optimize"

        if selected:
            self._expand_window(selected, mode)
        else:
            if not window_open and self._ball and not self._ball.isVisible():
                self._ball.show()
            self._expand_window(mode=mode)

    def _quit_app(self):
        remove_listener(self._rebuild_menus)
        self._running = False
        try:
            hotkey_manager.stop()
        except Exception as e:
            write_error(e, "_quit_app:hotkey_stop")
            pass
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
        from pathlib import Path
        icon_path = Path(__file__).parent / "assets" / "phraise_logo.png"
        if icon_path.exists():
            return QIcon(str(icon_path))
        from .theme import get_theme, theme_notifier
        colors = get_theme(theme_notifier.current_theme)["colors"]
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(colors["accent"]), 3))
        p.setBrush(QBrush(QColor(colors["bg_darker"])))
        p.drawEllipse(4, 4, size - 8, size - 8)
        font = QFont("Segoe UI", 19, QFont.Bold)
        font.setStyleHint(QFont.SansSerif)
        p.setFont(font)
        p.setPen(QColor(colors["white"]))
        p.drawText(pixmap.rect(), Qt.AlignCenter, "AI")
        p.end()
        return QIcon(pixmap)


def main():
    import multiprocessing
    multiprocessing.freeze_support()

    # Initialize COM MTA on the main Qt thread so UIA operations
    # (capture_foreground, focus_foreground, replace_text) work when
    # dispatched to the main thread via run_on_main().
    import sys as _sys
    if _sys.platform == "win32":
        try:
            import pythoncom
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        except pythoncom.error:
            pass  # Already initialized or incompatible model — continue

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    from .dispatch import init as init_dispatch
    init_dispatch()

    app.setStyle("Fusion")

    raw_theme = config.get("appearance", "theme", default="dark")
    theme_name = resolve_theme_name(raw_theme)
    theme = get_theme(theme_name)
    app.setPalette(palette_for_theme(theme))

    custom_css = config.get("appearance", "custom_css", default="")
    _ = apply_theme(theme_name, app=app, custom_css=custom_css)

    def _on_theme_changed(new_name: str) -> None:
        theme = get_theme(new_name)
        app.setPalette(palette_for_theme(theme))
        stylesheet = generate_app_stylesheet(theme["colors"])
        live_css = config.get("appearance", "custom_css", default="")
        if live_css:
            stylesheet += "\n" + live_css
        app.setStyleSheet(stylesheet)

    theme_notifier.theme_changed.connect(_on_theme_changed)

    from .harper_client import HarperClient
    app.aboutToQuit.connect(lambda: HarperClient.shutdown_all())

    phr_app = PhrAIseApp()
    phr_app.run()


def palette_for_theme(theme: FullTheme) -> QPalette:
    """Build a QPalette that maps theme color roles to Qt palette roles."""
    colors = theme["colors"]
    p = QPalette()
    p.setColor(QPalette.Window, QColor(colors["bg"]))
    p.setColor(QPalette.WindowText, QColor(colors["text"]))
    p.setColor(QPalette.Base, QColor(colors["bg_darker"]))
    p.setColor(QPalette.AlternateBase, QColor(colors["surface"]))
    p.setColor(QPalette.Text, QColor(colors["text"]))
    p.setColor(QPalette.Button, QColor(colors["surface"]))
    p.setColor(QPalette.ButtonText, QColor(colors["text"]))
    p.setColor(QPalette.Highlight, QColor(colors["accent"]))
    p.setColor(QPalette.HighlightedText, QColor(colors["white"]))
    p.setColor(QPalette.ToolTipBase, QColor(colors["surface"]))
    p.setColor(QPalette.ToolTipText, QColor(colors["text"]))
    p.setColor(QPalette.Link, QColor(colors["accent"]))
    return p


if __name__ == "__main__":
    main()
