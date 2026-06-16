# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Draggable always-on-top floating ball widget.
from collections.abc import Callable
from pathlib import Path

import qtawesome as qta

from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QRegion, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from .config import config
from .theme import get_theme, theme_notifier

ICON_PATH = Path(__file__).parent / "assets" / "phraise_logo.png"
ICON_PATH_PNG = ICON_PATH
ICON_PATH_SVG = Path(__file__).parent / "assets" / "phraise_logo.svg"


class FloatingBall(QWidget):
    """Draggable floating ball that stays on top of all windows."""

    def __init__(self, on_click: Callable | None = None, on_right_click: Callable | None = None):
        super().__init__()
        self._on_click = on_click
        self._on_right_click = on_right_click

        ball_size = config.get("floating_ball", "size", default=52)
        opacity = config.get("floating_ball", "opacity", default=0.50)
        pos_x = config.get("floating_ball", "position_x", default=1800)
        pos_y = config.get("floating_ball", "position_y", default=500)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(opacity)
        self.setFixedSize(ball_size, ball_size)
        self.move(pos_x, pos_y)

        mask = QRegion(QRect(0, 0, ball_size, ball_size), QRegion.Ellipse)
        self.setMask(mask)

        self._dragging = False
        self._drag_start = QPoint()
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._single_click)
        self._pending_click = False

        self._icon = None
        try:
            from PySide6.QtSvg import QSvgRenderer
            if ICON_PATH_SVG.exists():
                renderer = QSvgRenderer(str(ICON_PATH_SVG))
                pm = QPixmap(ball_size, ball_size)
                pm.fill(Qt.transparent)
                p = QPainter(pm)
                if renderer.render(p):
                    self._icon = pm
                p.end()
        except ImportError:
            pass  # QSvgRenderer not available; fall back to PNG/text.
        if self._icon is None and ICON_PATH_PNG.exists():
            self._icon = QPixmap(str(ICON_PATH_PNG))

        self._theme_colors = get_theme(theme_notifier.current_theme)["colors"]
        theme_notifier.theme_changed.connect(self._on_theme_changed)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        size = self.width()
        margin = 2
        accent_color = QColor(self._theme_colors["accent"])

        p.setPen(QPen(accent_color.lighter(120), 2))
        p.setBrush(QColor(self._theme_colors["bg"]))
        p.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)

        if self._icon:
            icon_size = int(size * 0.55)
            x = (size - icon_size) // 2
            y = (size - icon_size) // 2
            scaled = self._icon.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(x, y, scaled)
        else:
            center = size // 2
            text_size = max(10, size // 4)
            font = QFont("Segoe UI", text_size, QFont.Bold)
            font.setStyleHint(QFont.SansSerif)
            p.setFont(font)
            p.setPen(QColor(self._theme_colors["text"]))
            p.drawText(QRect(0, 0, size, size - 2), Qt.AlignCenter, "AI")
            pencil_size = max(12, int(size * 0.3))
            pencil_pm = qta.icon("fa5s.pencil-alt", color=accent_color).pixmap(pencil_size, pencil_size)
            px = (size - pencil_size) // 2
            py = center + text_size // 2
            p.drawPixmap(px, py, pencil_pm)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._dragging = False
        elif event.button() == Qt.RightButton and self._on_right_click:
            self._on_right_click(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_start
            if abs(delta.x()) > 3 or abs(delta.y()) > 3:
                self._dragging = True
                self._pending_click = False
                self._click_timer.stop()
            self.move(self.pos() + delta)
            self._drag_start = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._dragging:
                if self._pending_click:
                    self._pending_click = False
                    self._click_timer.stop()
                    if self._on_click:
                        self._on_click()
                else:
                    self._pending_click = True
                    self._click_timer.start(400)
            self._save_position()

    def mouseDoubleClickEvent(self, event):
        self._pending_click = False
        self._click_timer.stop()
        if self._on_click:
            self._on_click()

    def _single_click(self):
        self._pending_click = False

    def _on_theme_changed(self, name: str) -> None:
        self._theme_colors = get_theme(name)["colors"]
        self.update()

    def _save_position(self):
        config.update_section("floating_ball", {
            "position_x": self.x(),
            "position_y": self.y(),
        })

    def show_ball(self):
        self.show()

    def hide_ball(self):
        self.hide()

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def set_opacity(self, opacity: float):
        self.setWindowOpacity(max(0.1, min(1.0, opacity)))

    @property
    def root(self):
        return QApplication.instance()
