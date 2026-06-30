# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Main floating window UI for optimize and translate results.
from .config import config
from .dispatch import run_on_main
from .error_log import write_error
from .harper_client import LintResult
from .harper_types import HarperIssue
from .i18n import t, SOURCE_LANGUAGES, TARGET_LANGUAGES, add_listener, remove_listener
from .llm_client import optimize_text, translate_text, custom_instruction, check_output_fit
from .text_grabber import TextGrabber
from .theme import (
    get_theme, theme_notifier,
    btn_style, action_btn_style, style_btn_style,
    combo_style, tab_style, text_edit_style,
    titlebar_style, scroll_area_style,
    label_style, separator_style, toast_style, rgba,
)

import html
import json
from collections.abc import Callable
from pathlib import Path

import qtawesome as qta

import shiboken6

from PySide6.QtCore import Qt, QPoint, QRect, QSize, QTimer, QEvent
from PySide6.QtGui import QColor, QHideEvent, QMouseEvent, QPainter, QPainterPath, QBrush, QPen, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTabWidget, QScrollArea, QTextEdit, QComboBox,
    QFrame, QSizePolicy, QLayout, QCheckBox
)


_INTERACTIVE_TYPES = (QComboBox, QPushButton, QCheckBox, QTextEdit)


class NoScrollComboBox(QComboBox):
    """QComboBox that blocks scroll wheel when the dropdown popup is closed."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup_open = False

    def showPopup(self):
        self._popup_open = True
        super().showPopup()

    def hidePopup(self):
        self._popup_open = False
        super().hidePopup()

    def wheelEvent(self, event):
        if self._popup_open:
            super().wheelEvent(event)
        else:
            event.ignore()


class FlowLayout(QLayout):
    """Wrapping flow layout — items flow left-to-right, wrap to next row.

    Standard Qt FlowLayout pattern adapted for PySide6.
    """
    def __init__(self, parent=None, margin=0, spacing=4):
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only=False):
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = r.x()
        y = r.y()
        line_h = 0
        max_right = r.right()

        for item in self._items:
            ih = item.sizeHint()
            next_x = x + ih.width() + self._spacing
            if next_x - self._spacing > max_right + 1 and line_h > 0:
                x = r.x()
                y = y + line_h + self._spacing
                next_x = x + ih.width() + self._spacing
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), ih))
            x = next_x
            line_h = max(line_h, ih.height())

        return y + line_h - rect.y() + m.bottom()


class _DragBar(QWidget):
    def __init__(self, window: QWidget, height: int = 36):
        super().__init__(window)
        self._window = window
        self._dragging = False
        self._drag_start = QPoint()
        self.setFixedHeight(height)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.globalPosition().toPoint()
            self.grabMouse()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            gpos = event.globalPosition().toPoint()
            delta = gpos - self._drag_start
            if delta.x() != 0 or delta.y() != 0:
                w = self._window
                w.move(w.pos() + delta)
                self._drag_start = gpos
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._dragging:
            self._dragging = False
            self.releaseMouse()
            self._window._save_geometry()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def hideEvent(self, event: QHideEvent):
        if self._dragging:
            self._dragging = False
            self.releaseMouse()
        super().hideEvent(event)


class _HoverTextEdit(QWidget):
    """Text edit with hover-reveal action buttons (replace / copy)."""

    def __init__(self, parent, on_replace, on_copy, theme_colors):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._theme_colors = theme_colors

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMinimumHeight(80)
        self.text_edit.setMaximumHeight(300)
        self.text_edit.setFixedHeight(100)
        self.text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.text_edit.setStyleSheet(text_edit_style(theme_colors))
        self.text_edit.setMouseTracking(True)

        self._btn_overlay = QWidget(self)
        self._btn_overlay.setStyleSheet(
            f"background: {rgba(theme_colors['surface'], 220)}; border-radius: 4px; padding: 2px;")
        self._btn_overlay.setMouseTracking(True)
        btn_layout = QHBoxLayout(self._btn_overlay)
        btn_layout.setContentsMargins(4, 2, 4, 2)
        btn_layout.setSpacing(4)

        self._replace_btn = QPushButton(t("fw.btn.replace"))
        self._replace_btn.setFixedSize(80, 22)
        self._replace_btn.setStyleSheet(action_btn_style(theme_colors, "accent"))
        self._replace_btn.clicked.connect(lambda: on_replace(self.text_edit.toPlainText()))
        btn_layout.addWidget(self._replace_btn)

        copy_btn = QPushButton(t("fw.btn.copy"))
        copy_btn.setFixedSize(48, 22)
        copy_btn.setStyleSheet(action_btn_style(theme_colors, "surface"))
        copy_btn.clicked.connect(lambda: on_copy(self.text_edit))
        btn_layout.addWidget(copy_btn)

        self._btn_overlay.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_edit)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def enterEvent(self, event):
        self._btn_overlay.show()
        self._btn_overlay.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._btn_overlay.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        oh = self._btn_overlay.sizeHint().height()
        ow = self._btn_overlay.sizeHint().width()
        margin = 4
        self._btn_overlay.setGeometry(
            self.width() - ow - margin,
            self.height() - oh - margin,
            ow, oh,
        )

    def update_theme(self, tc):
        self._theme_colors = tc
        self.text_edit.setStyleSheet(text_edit_style(tc))
        self._btn_overlay.setStyleSheet(
            f"background: {rgba(tc['surface'], 220)}; border-radius: 4px; padding: 2px;")
        self._replace_btn.setStyleSheet(action_btn_style(tc, "accent"))


class FloatingWindow(QWidget):
    """Main floating window with optimize and translate tabs."""

    MODE_INDEX = {"optimize": 0, "translate": 1, "optimize_translate": 2}

    def __init__(self, grabber: TextGrabber, on_close: Callable | None = None):
        super().__init__()
        self._theme_colors = get_theme(theme_notifier.current_theme)["colors"]
        theme_notifier.theme_changed.connect(self._apply_theme)
        self._on_close = on_close
        self._grabber = grabber
        self._current_text: str = ""
        self._current_mode: str = "optimize"
        self._current_style: str = config.get("floating_window", "last_style", default="concise")
        self._is_loading: bool = False
        self._active_client = None
        self._pinned: bool = True
        self._model_combo = None

        self._setup_window()
        self._build_ui()
        self._install_resize_event_filter()
        _icon_path = Path(__file__).parent / "assets" / "phraise_logo.png"
        if _icon_path.exists():
            self.setWindowIcon(QIcon(str(_icon_path)))
        add_listener(self._retranslate_ui)

    @property
    def current_mode(self) -> str:
        """Return the current mode ('optimize' or 'translate')."""
        return self._current_mode

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowOpacity(config.get("floating_window", "opacity", default=0.95))
        self.setMouseTracking(True)

        w = config.get("floating_window", "width", default=400)
        h = config.get("floating_window", "height", default=500)
        x = config.get("floating_window", "position_x", default=1400)
        y = config.get("floating_window", "position_y", default=600)
        self.setGeometry(x, y, w, h)
        self.setMinimumSize(350, 380)
        self.setMaximumSize(1400, 1600)

        self._radius = 12
        self._bg_color = QColor(self._theme_colors["bg"])
        self._border_color = QColor(self._theme_colors["border"])
        self.setAutoFillBackground(False)

        self._drag_start = QPoint()
        self._drag_start_geo = QRect()
        self._resizing = False
        self._resize_edge = ""
        self._resize_margin = 6
        self._titlebar_height = 36

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        r = self._radius
        rect = self.rect().adjusted(1, 1, -1, -1)
        path.addRoundedRect(rect, r, r)
        p.setBrush(QBrush(self._bg_color))
        p.setPen(QPen(self._border_color, 1))
        p.drawPath(path)

        # Resize grip indicator (bottom-right corner)
        grip_margin = 8
        grip_size = 14
        grip_color = QColor(self._theme_colors["text_muted"])
        p.setPen(QPen(grip_color, 1))
        rx, ry = rect.right() - grip_margin, rect.bottom() - grip_margin
        for i in range(3):
            offset = i * 4
            p.drawLine(int(rx - grip_size + offset), ry, rx, int(ry - grip_size + offset))

    def _show_normal(self):
        self.show()
        QApplication.processEvents()
        self.raise_()
        QTimer.singleShot(50, self.activateWindow)

    def load_text(self, text: str, mode: str = "optimize"):
        if not text or not text.strip():
            return
        self._current_text = text
        self._tabs.setCurrentIndex(self.MODE_INDEX[mode])
        if mode == "translate":
            self._do_translate()
        elif mode == "optimize_translate":
            self._do_optimize_translate()
        else:
            self._do_optimize()
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._build_titlebar(main_layout)
        self._build_tabs(main_layout)

        footer = QWidget()
        footer.setFixedHeight(12)
        footer.setStyleSheet(
            f"background: {self._theme_colors['bg_darker']}; border-bottom: 1px solid {self._theme_colors['border']};"
            f"border-bottom-left-radius: {self._radius}px;"
            f"border-bottom-right-radius: {self._radius}px;")
        main_layout.addWidget(footer)

        self._loading_overlay = QWidget(self)
        self._loading_overlay.setStyleSheet(
            f"background: {rgba(self._theme_colors['bg'], 200)}; border-radius: 8px;")
        self._loading_overlay.hide()
        overlay_layout = QVBoxLayout(self._loading_overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)
        self._loading_label = QLabel(f"\u23f3 {t('fw.loading')}")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setStyleSheet(label_style(self._theme_colors, "text", "font-size: 16px; font-weight: 600; border: none;"))
        overlay_layout.addWidget(self._loading_label)

    def _build_titlebar(self, layout: QVBoxLayout):
        self._drag_bar = _DragBar(self, self._titlebar_height)
        self._drag_bar.setStyleSheet(titlebar_style(self._theme_colors, self._radius))
        bar_layout = QHBoxLayout(self._drag_bar)
        bar_layout.setContentsMargins(12, 0, 4, 0)

        self._title_label = QLabel(t("fw.title"))
        self._title_label.setStyleSheet(label_style(self._theme_colors, "text", "font-weight: 600; font-size: 13px;"))
        bar_layout.addWidget(self._title_label)
        bar_layout.addStretch()

        regen_btn = QPushButton()
        regen_btn.setFixedSize(32, 28)
        regen_btn.setIcon(qta.icon("fa5s.redo", color=self._theme_colors["text_muted"]))
        regen_btn.setIconSize(regen_btn.size() * 0.5)
        regen_btn.setStyleSheet(btn_style(self._theme_colors))
        regen_btn.clicked.connect(self._on_regenerate)
        bar_layout.addWidget(regen_btn)
        self._regenerate_btn = regen_btn

        settings_btn = QPushButton()
        settings_btn.setFixedSize(32, 28)
        settings_btn.setIcon(qta.icon("fa5s.cog", color=self._theme_colors["text_muted"]))
        settings_btn.setIconSize(settings_btn.size() * 0.55)
        settings_btn.setStyleSheet(btn_style(self._theme_colors))
        settings_btn.clicked.connect(self._on_settings)
        bar_layout.addWidget(settings_btn)

        pin_btn = QPushButton()
        pin_btn.setFixedSize(32, 28)
        pin_btn.setIcon(qta.icon("fa5s.thumbtack", color=self._theme_colors["text_muted"]))
        pin_btn.setIconSize(pin_btn.size() * 0.55)
        pin_btn.setStyleSheet(btn_style(self._theme_colors))
        pin_btn.clicked.connect(self._toggle_pin)
        bar_layout.addWidget(pin_btn)

        min_btn = QPushButton()
        min_btn.setFixedSize(32, 28)
        min_btn.setIcon(qta.icon("fa5s.window-minimize", color=self._theme_colors["text_muted"]))
        min_btn.setIconSize(min_btn.size() * 0.45)
        min_btn.setStyleSheet(btn_style(self._theme_colors))
        min_btn.clicked.connect(self._close)
        bar_layout.addWidget(min_btn)
        self._min_btn = min_btn

        close_btn = QPushButton()
        close_btn.setFixedSize(32, 28)
        close_btn.setIcon(qta.icon("fa5s.times", color=self._theme_colors["red"]))
        close_btn.setIconSize(close_btn.size() * 0.55)
        close_btn.setStyleSheet(btn_style(self._theme_colors, "red"))
        close_btn.clicked.connect(self._close)
        bar_layout.addWidget(close_btn)
        self._close_btn = close_btn
        self._pin_btn = pin_btn
        self._settings_btn = settings_btn

        layout.addWidget(self._drag_bar)

    def _build_tabs(self, layout: QVBoxLayout):
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(tab_style(self._theme_colors))
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._build_optimize_tab()
        self._build_translate_tab()
        self._build_optimize_translate_tab()

        corner = QWidget()
        corner.setFixedSize(148, 30)
        self._model_combo = NoScrollComboBox(corner)
        self._model_combo.setFixedWidth(140)
        self._model_combo.move(4, 2)
        self._model_combo.setStyleSheet(combo_style(self._theme_colors))
        self._model_combo.currentIndexChanged.connect(self._on_model_combo_changed)
        self._refresh_model_combo()
        self._tabs.setCornerWidget(corner, Qt.TopRightCorner)

        layout.addWidget(self._tabs, 1)

    def _build_optimize_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scroll_area_style(self._theme_colors))

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        styles = config.get("styles", default=[])
        style_widget = QWidget()
        style_layout = FlowLayout(style_widget, spacing=4)
        style_layout.setContentsMargins(0, 0, 0, 0)
        self._style_label = QLabel(t("fw.label.style"))
        self._style_label.setStyleSheet(label_style(self._theme_colors, "text_muted", "font-size: 12px; font-weight: 500;"))
        style_layout.addWidget(self._style_label)
        self._style_buttons: dict[str, QPushButton] = {}
        for s in styles:
            sid = s["id"]
            label = t(f"style.{sid}")
            if label == f"style.{sid}":
                label = s.get("label", sid)
            btn = QPushButton(label)
            btn.setFixedSize(80, 26)
            active = sid == self._current_style
            btn.setStyleSheet(style_btn_style(self._theme_colors, active))
            btn.clicked.connect(lambda checked, sid=sid: self._on_style_change(sid))
            style_layout.addWidget(btn)
            self._style_buttons[sid] = btn
        self._style_widget = style_widget
        layout.addWidget(style_widget)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(separator_style(self._theme_colors))
        layout.addWidget(sep)

        # Grammar issues section
        self._grammar_header = QLabel(t("fw.label.grammar_expanded"))
        self._grammar_header.setStyleSheet(label_style(self._theme_colors, "text_muted", "font-size: 13px; font-weight: 600; margin-top: 6px;"))
        self._grammar_header.setCursor(Qt.PointingHandCursor)
        self._grammar_header.mousePressEvent = lambda e: self._toggle_grammar_section()
        layout.addWidget(self._grammar_header)

        self._grammar_container = QWidget()
        self._grammar_layout = QVBoxLayout(self._grammar_container)
        self._grammar_layout.setContentsMargins(0, 4, 0, 4)
        self._grammar_layout.setSpacing(6)
        layout.addWidget(self._grammar_container)

        self._grammar_header.hide()
        self._grammar_container.hide()

        self._rewrite_label = QLabel(t("fw.label.rewrites"))
        layout.addWidget(self._rewrite_label)
        self._rewrite_texts: list[_HoverTextEdit] = []
        for i in range(3):
            hover_edit = _HoverTextEdit(container, self._do_replace, self._on_copy_text, self._theme_colors)
            hover_edit.text_edit.textChanged.connect(
                lambda he=hover_edit: FloatingWindow._auto_resize_text_edit(he.text_edit))
            layout.addWidget(hover_edit)
            self._rewrite_texts.append(hover_edit)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(separator_style(self._theme_colors))
        layout.addWidget(sep2)

        self._custom_instruction_label = QLabel(t("fw.label.custom_instruction"))
        layout.addWidget(self._custom_instruction_label)
        self._custom_entry = QTextEdit()
        self._custom_entry.setMinimumHeight(40)
        self._custom_entry.setMaximumHeight(120)
        self._custom_entry.setFixedHeight(40)
        self._custom_entry.setStyleSheet(text_edit_style(self._theme_colors))
        self._custom_entry.textChanged.connect(lambda: FloatingWindow._auto_resize_text_edit(self._custom_entry))
        layout.addWidget(self._custom_entry)

        self._custom_btn = QPushButton(t("fw.btn.generate"))
        self._custom_btn.setFixedSize(80, 26)
        self._custom_btn.setStyleSheet(action_btn_style(self._theme_colors, "surface"))
        self._custom_btn.clicked.connect(self._on_custom_generate)
        layout.addWidget(self._custom_btn)
        layout.addStretch()

        scroll.setWidget(container)
        self._tabs.addTab(scroll, t("fw.tab.optimize"))
        self._optimize_scroll = scroll

    def _build_translate_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scroll_area_style(self._theme_colors))

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        lang_widget = QWidget()
        lang_layout = QHBoxLayout(lang_widget)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        self._source_lang_label = QLabel(t("fw.label.source_lang"))
        lang_layout.addWidget(self._source_lang_label)
        self._source_lang = NoScrollComboBox()
        self._source_lang.setFixedWidth(140)  # wider for full names
        self._source_lang.setStyleSheet(combo_style(self._theme_colors))
        for display_name, code in SOURCE_LANGUAGES:
            self._source_lang.addItem(display_name, code)
        # Set current based on saved config code
        saved_source = config.get("translation", "source_lang", default="auto")
        # Handle legacy "en" → "en-US" migration
        if saved_source == "en":
            saved_source = "en-US"
        idx = self._source_lang.findData(saved_source)
        if idx >= 0:
            self._source_lang.setCurrentIndex(idx)
        lang_layout.addWidget(self._source_lang)
        self._target_lang_label = QLabel(t("fw.label.target_lang"))
        lang_layout.addWidget(self._target_lang_label)
        self._target_lang = NoScrollComboBox()
        self._target_lang.setFixedWidth(140)  # wider for full names
        self._target_lang.setStyleSheet(combo_style(self._theme_colors))
        for display_name, code in TARGET_LANGUAGES:
            self._target_lang.addItem(display_name, code)
        saved_target = config.get("translation", "target_lang", default="zh-CN")
        if saved_target == "en":
            saved_target = "en-US"
        idx = self._target_lang.findData(saved_target)
        if idx >= 0:
            self._target_lang.setCurrentIndex(idx)
        lang_layout.addWidget(self._target_lang)
        lang_layout.addStretch()
        self._source_lang.currentIndexChanged.connect(
            lambda: config.set("translation", "source_lang",
                               value=self._source_lang.currentData() or "auto"))
        self._target_lang.currentIndexChanged.connect(
            lambda: config.set("translation", "target_lang",
                               value=self._target_lang.currentData() or "zh-CN"))

        layout.addWidget(lang_widget)

        # Persist language selections on change
        self._source_lang.currentIndexChanged.connect(
            lambda: config.set("translation", "source_lang",
                               value=self._source_lang.currentData() or "auto"))
        self._target_lang.currentIndexChanged.connect(
            lambda: config.set("translation", "target_lang",
                               value=self._target_lang.currentData() or "zh-CN"))

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(separator_style(self._theme_colors))
        layout.addWidget(sep)

        self._translation_result_label = QLabel(t("fw.label.translation_result"))
        layout.addWidget(self._translation_result_label)
        self._translation_text = QTextEdit()
        self._translation_text.setReadOnly(True)
        self._translation_text.setMinimumHeight(60)
        self._translation_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._translation_text.setStyleSheet(text_edit_style(self._theme_colors))
        layout.addWidget(self._translation_text, 1)

        trans_btn_row = QWidget()
        trans_btn_layout = QHBoxLayout(trans_btn_row)
        trans_btn_layout.setContentsMargins(0, 4, 0, 0)
        self._trans_replace_btn = QPushButton(t("fw.btn.replace_original"))
        self._trans_replace_btn.setFixedSize(130, 24)
        self._trans_replace_btn.setStyleSheet(action_btn_style(self._theme_colors, "accent"))
        self._trans_replace_btn.clicked.connect(lambda checked=False: self._do_replace(self._translation_text.toPlainText()))
        trans_btn_layout.addWidget(self._trans_replace_btn)
        self._trans_copy_btn = QPushButton(t("fw.btn.copy"))
        self._trans_copy_btn.setFixedSize(50, 24)
        self._trans_copy_btn.setStyleSheet(action_btn_style(self._theme_colors, "surface"))
        self._trans_copy_btn.clicked.connect(lambda checked=False: self._on_copy_text(self._translation_text))
        trans_btn_layout.addWidget(self._trans_copy_btn)
        trans_btn_layout.addStretch()
        layout.addWidget(trans_btn_row)

        scroll.setWidget(container)
        self._tabs.addTab(scroll, t("fw.tab.translate"))
        self._translate_scroll = scroll

    def _build_optimize_translate_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(scroll_area_style(self._theme_colors))

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        optimize_header_row = QWidget()
        optimize_header_layout = QHBoxLayout(optimize_header_row)
        optimize_header_layout.setContentsMargins(0, 0, 0, 0)
        self._combined_optimize_label = QLabel(t("fw.label.optimize_section"))
        self._combined_optimize_label.setStyleSheet(
            label_style(self._theme_colors, "text", "font-size: 13px; font-weight: 600;")
        )
        optimize_header_layout.addWidget(self._combined_optimize_label)
        self._combined_optimize_loading = QLabel()
        self._combined_optimize_loading.setPixmap(
            qta.icon("fa5s.spinner", color=self._theme_colors["yellow"]).pixmap(QSize(16, 16))
        )
        self._combined_optimize_loading.hide()
        optimize_header_layout.addWidget(self._combined_optimize_loading)
        optimize_header_layout.addStretch()
        layout.addWidget(optimize_header_row)

        styles = config.get("styles", default=[])
        style_widget = QWidget()
        style_layout = FlowLayout(style_widget, spacing=4)
        style_layout.setContentsMargins(0, 0, 0, 0)
        self._combined_style_label = QLabel(t("fw.label.style"))
        self._combined_style_label.setStyleSheet(
            label_style(self._theme_colors, "text_muted", "font-size: 12px; font-weight: 500;")
        )
        style_layout.addWidget(self._combined_style_label)
        self._combined_style_buttons: dict[str, QPushButton] = {}
        for s in styles:
            sid = s["id"]
            label = t(f"style.{sid}")
            if label == f"style.{sid}":
                label = s.get("label", sid)
            btn = QPushButton(label)
            btn.setFixedSize(80, 26)
            active = sid == self._current_style
            btn.setStyleSheet(style_btn_style(self._theme_colors, active))
            btn.clicked.connect(lambda checked, sid=sid: self._on_style_change(sid))
            style_layout.addWidget(btn)
            self._combined_style_buttons[sid] = btn
        self._combined_style_widget = style_widget
        layout.addWidget(style_widget)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(separator_style(self._theme_colors))
        layout.addWidget(sep)

        self._combined_grammar_header = QLabel(t("fw.label.grammar_expanded"))
        self._combined_grammar_header.setStyleSheet(
            label_style(self._theme_colors, "text_muted", "font-size: 13px; font-weight: 600; margin-top: 6px;")
        )
        self._combined_grammar_header.setCursor(Qt.PointingHandCursor)
        self._combined_grammar_header.mousePressEvent = lambda e: self._toggle_combined_grammar_section()
        layout.addWidget(self._combined_grammar_header)

        self._combined_grammar_container = QWidget()
        self._combined_grammar_layout = QVBoxLayout(self._combined_grammar_container)
        self._combined_grammar_layout.setContentsMargins(0, 4, 0, 4)
        self._combined_grammar_layout.setSpacing(6)
        layout.addWidget(self._combined_grammar_container)

        self._combined_grammar_header.hide()
        self._combined_grammar_container.hide()

        self._combined_rewrite_label = QLabel(t("fw.label.rewrites"))
        layout.addWidget(self._combined_rewrite_label)
        self._combined_rewrite_texts: list[_HoverTextEdit] = []
        for _ in range(3):
            hover_edit = _HoverTextEdit(container, self._do_replace, self._on_copy_text, self._theme_colors)
            hover_edit.text_edit.textChanged.connect(
                lambda he=hover_edit: FloatingWindow._auto_resize_text_edit(he.text_edit)
            )
            layout.addWidget(hover_edit)
            self._combined_rewrite_texts.append(hover_edit)

        translate_sep = QFrame()
        translate_sep.setFrameShape(QFrame.HLine)
        translate_sep.setStyleSheet(separator_style(self._theme_colors))
        layout.addWidget(translate_sep)

        translate_header_row = QWidget()
        translate_header_layout = QHBoxLayout(translate_header_row)
        translate_header_layout.setContentsMargins(0, 0, 0, 0)
        self._combined_translate_label = QLabel(t("fw.label.translate_section"))
        self._combined_translate_label.setStyleSheet(
            label_style(self._theme_colors, "text", "font-size: 13px; font-weight: 600;")
        )
        translate_header_layout.addWidget(self._combined_translate_label)
        self._combined_translate_loading = QLabel()
        self._combined_translate_loading.setPixmap(
            qta.icon("fa5s.spinner", color=self._theme_colors["yellow"]).pixmap(QSize(16, 16))
        )
        self._combined_translate_loading.hide()
        translate_header_layout.addWidget(self._combined_translate_loading)
        translate_header_layout.addStretch()
        layout.addWidget(translate_header_row)

        lang_widget = QWidget()
        lang_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        lang_layout = QHBoxLayout(lang_widget)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        self._combined_source_lang_label = QLabel(t("fw.label.source_lang"))
        lang_layout.addWidget(self._combined_source_lang_label)
        self._combined_source_lang = NoScrollComboBox()
        self._combined_source_lang.setFixedWidth(140)
        self._combined_source_lang.setStyleSheet(combo_style(self._theme_colors))
        for display_name, code in SOURCE_LANGUAGES:
            self._combined_source_lang.addItem(display_name, code)
        saved_source = config.get("translation", "source_lang", default="auto")
        if saved_source == "en":
            saved_source = "en-US"
        idx = self._combined_source_lang.findData(saved_source)
        if idx >= 0:
            self._combined_source_lang.setCurrentIndex(idx)
        lang_layout.addWidget(self._combined_source_lang)
        self._combined_target_lang_label = QLabel(t("fw.label.target_lang"))
        lang_layout.addWidget(self._combined_target_lang_label)
        self._combined_target_lang = NoScrollComboBox()
        self._combined_target_lang.setFixedWidth(140)
        self._combined_target_lang.setStyleSheet(combo_style(self._theme_colors))
        for display_name, code in TARGET_LANGUAGES:
            self._combined_target_lang.addItem(display_name, code)
        saved_target = config.get("translation", "target_lang", default="zh-CN")
        if saved_target == "en":
            saved_target = "en-US"
        idx = self._combined_target_lang.findData(saved_target)
        if idx >= 0:
            self._combined_target_lang.setCurrentIndex(idx)
        lang_layout.addWidget(self._combined_target_lang)
        lang_layout.addStretch()
        layout.addWidget(lang_widget)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(separator_style(self._theme_colors))
        layout.addWidget(sep2)

        self._combined_translation_result_label = QLabel(t("fw.label.translation_result"))
        layout.addWidget(self._combined_translation_result_label)
        self._combined_translation_text = QTextEdit()
        self._combined_translation_text.setReadOnly(True)
        self._combined_translation_text.setMinimumHeight(60)
        self._combined_translation_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._combined_translation_text.setStyleSheet(text_edit_style(self._theme_colors))
        layout.addWidget(self._combined_translation_text, 1)

        trans_btn_row = QWidget()
        trans_btn_layout = QHBoxLayout(trans_btn_row)
        trans_btn_layout.setContentsMargins(0, 4, 0, 0)
        self._combined_trans_replace_btn = QPushButton(t("fw.btn.replace_original"))
        self._combined_trans_replace_btn.setFixedSize(130, 24)
        self._combined_trans_replace_btn.setStyleSheet(action_btn_style(self._theme_colors, "accent"))
        self._combined_trans_replace_btn.clicked.connect(lambda checked=False: self._do_replace(self._combined_translation_text.toPlainText()))
        trans_btn_layout.addWidget(self._combined_trans_replace_btn)
        self._combined_trans_copy_btn = QPushButton(t("fw.btn.copy"))
        self._combined_trans_copy_btn.setFixedSize(50, 24)
        self._combined_trans_copy_btn.setStyleSheet(action_btn_style(self._theme_colors, "surface"))
        self._combined_trans_copy_btn.clicked.connect(lambda checked=False: self._on_copy_text(self._combined_translation_text))
        trans_btn_layout.addWidget(self._combined_trans_copy_btn)
        trans_btn_layout.addStretch()
        layout.addWidget(trans_btn_row)

        layout.addStretch()

        scroll.setWidget(container)
        self._tabs.addTab(scroll, t("fw.tab.optimize_translate"))
        self._combined_scroll = scroll

    def _toggle_combined_grammar_section(self):
        if self._combined_grammar_container.isVisible():
            self._combined_grammar_container.hide()
            self._combined_grammar_header.setText(t("fw.label.grammar_collapsed"))
        else:
            self._combined_grammar_container.show()
            self._combined_grammar_header.setText(t("fw.label.grammar_expanded"))

    # ---- Event handlers ----

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            return
        self._on_resize_press(event.position().toPoint(), event.globalPosition().toPoint())

    def _on_resize_press(self, pos: QPoint, gpos: QPoint):
        edge = self._get_resize_edge(pos)
        if edge:
            self._resizing = True
            self._resize_edge = edge
            self._drag_start = gpos
            self._drag_start_geo = QRect(self.geometry())
        else:
            self._resizing = False
            self._resize_edge = ""

    def mouseMoveEvent(self, event: QMouseEvent):
        self._on_resize_move(event.position().toPoint(), event.globalPosition().toPoint())

    def _on_resize_move(self, pos: QPoint, gpos: QPoint, cursor_widget: QWidget | None = None):
        if self._resizing and self._resize_edge:
            delta = gpos - self._drag_start
            geo = self._drag_start_geo
            x, y, w, h = geo.x(), geo.y(), geo.width(), geo.height()
            if "e" in self._resize_edge:
                w = max(350, w + delta.x())
            if "s" in self._resize_edge:
                h = max(380, h + delta.y())
            if "w" in self._resize_edge:
                w = max(350, w - delta.x())
                x += delta.x()
            if "n" in self._resize_edge:
                h = max(380, h - delta.y())
                y += delta.y()
            self.setGeometry(x, y, w, h)
            self._drag_start = gpos
            self._drag_start_geo = QRect(self.geometry())
            edge = self._resize_edge
        else:
            edge = self._get_resize_edge(pos)

        if ("e" in edge and "s" in edge) or ("w" in edge and "n" in edge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif "e" in edge and "n" in edge:
            self.setCursor(Qt.SizeBDiagCursor)
        elif "w" in edge and "s" in edge:
            self.setCursor(Qt.SizeBDiagCursor)
        elif "e" in edge or "w" in edge:
            self.setCursor(Qt.SizeHorCursor)
        elif "s" in edge or "n" in edge:
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()

        if cursor_widget is not None:
            if edge:
                cursor_widget.setCursor(self.cursor())
            else:
                cursor_widget.unsetCursor()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._on_resize_release()

    def _on_resize_release(self):
        self._resizing = False
        self._resize_edge = ""
        self._save_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay'):
            title_h = self._titlebar_height
            margin = 2
            bw = self.width() - margin * 2
            bh = self.height() - title_h - margin
            self._loading_overlay.setGeometry(margin, title_h, bw, max(0, bh))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._close()

    def _get_resize_edge(self, pos: QPoint):
        w, h = self.width(), self.height()
        m = self._resize_margin
        edge = ""
        if pos.x() >= w - m:
            edge += "e"
        elif pos.x() <= m:
            edge += "w"
        if pos.y() >= h - m:
            edge += "s"
        elif pos.y() <= m:
            edge += "n"
        return edge if edge else ""

    def _has_interactive_ancestor(self, child: QWidget, root: QWidget) -> bool:
        """Return True if *child* has any ancestor (up to but not including *root*)
        that is an instance of *INTERACTIVE_TYPES*."""
        parent = child.parent()
        while parent and parent is not root:
            if isinstance(parent, _INTERACTIVE_TYPES):
                return True
            parent = parent.parent()
        return False

    def _install_resize_event_filter(self, widget: QWidget | None = None):
        if widget is None:
            widget = self
        widget.installEventFilter(self)
        widget.setMouseTracking(True)
        for child in widget.children():
            if not isinstance(child, QWidget):
                continue
            if isinstance(child, _INTERACTIVE_TYPES) or self._has_interactive_ancestor(child, widget):
                continue
            child.installEventFilter(self)
            child.setMouseTracking(True)

    def eventFilter(self, watched, event):
        if watched is self:
            return False
        if not isinstance(watched, QWidget):
            return False
        if isinstance(watched, _INTERACTIVE_TYPES) or self._has_interactive_ancestor(watched, self):
            return False
        if event.type() not in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            return False

        local_pos = watched.mapTo(self, event.position().toPoint())
        edge = self._get_resize_edge(local_pos)
        gpos = event.globalPosition().toPoint()

        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton and edge:
                self._on_resize_press(local_pos, gpos)
                return True
            return False

        if event.type() == QEvent.MouseMove:
            if self._resizing or edge:
                self._on_resize_move(local_pos, gpos, cursor_widget=watched)
                return True
            watched.unsetCursor()
            return False

        if event.type() == QEvent.MouseButtonRelease:
            if self._resizing:
                self._on_resize_release()
                return True
            return False

        return False
    # ---- Tab & style ----

    def _on_tab_changed(self, idx):
        for mode, index in self.MODE_INDEX.items():
            if index == idx:
                self._current_mode = mode
                break
        config.set("floating_window", "last_tab", value=self._current_mode)
        if hasattr(self, '_model_combo') and self._model_combo is not None:
            self._refresh_model_combo()

    def _toggle_grammar_section(self):
        if self._grammar_container.isVisible():
            self._grammar_container.hide()
            self._grammar_header.setText(t("fw.label.grammar_collapsed"))
        else:
            self._grammar_container.show()
            self._grammar_header.setText(t("fw.label.grammar_expanded"))

    def _populate_grammar_issues(self, issues: list):
        while self._grammar_layout.count():
            item = self._grammar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        self._grammar_header.show()
        self._grammar_container.show()
        self._grammar_header.setText(t("fw.label.grammar_expanded"))

        self._grammar_issues = list(issues)

        self._recompute_corrected_text()

        if not issues:
            no_issues = QLabel(t("fw.no_issues"))
            no_issues.setStyleSheet(label_style(self._theme_colors, "green", "font-size: 12px; font-weight: 500;"))
            self._grammar_layout.addWidget(no_issues)
            return

        for issue in issues:
            row = self._build_issue_row(issue)
            self._grammar_layout.addWidget(row)

    def _build_issue_row(self, issue) -> QWidget:
        if isinstance(issue, HarperIssue):
            original = issue.original
            suggestion = issue.suggestion
            reason = issue.reason
            severity = issue.severity
            enabled = issue.enabled
            has_edit = issue.edit is not None
        else:
            original = issue.get("original", "")
            suggestion = issue.get("suggestion", "")
            reason = issue.get("reason", "")
            severity = issue.get("severity", "warning")
            enabled = issue.get("enabled", True)
            has_edit = bool(suggestion)

        original_escaped = html.escape(original)
        suggestion_escaped = html.escape(suggestion)
        reason_escaped = html.escape(reason) if reason else ""

        row = QWidget()
        row.setStyleSheet(
            f"background: {self._theme_colors['surface']}; border: 1px solid {self._theme_colors['border']}; "
            f"border-radius: 4px; padding: 2px;"
        )
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(3, 2, 3, 2)
        row_layout.setSpacing(6)

        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        badge_color = self._theme_colors["red"] if severity == "error" else self._theme_colors["orange"]
        main_html = (
            f"<span style='color:{badge_color};font-size:11px;'>&#9679;</span> "
            f"<s style='color:{self._theme_colors['red']};font-size:11px;'>{original_escaped}</s>"
        )
        if suggestion_escaped:
            main_html += (
                f" <span style='color:{self._theme_colors['green']};font-size:11px;'>&#8594; {suggestion_escaped}</span>"
            )
        main_label = QLabel(main_html)
        main_label.setWordWrap(True)
        main_label.setTextFormat(Qt.RichText)
        main_label.setStyleSheet(f"font-size: 11px; color: {self._theme_colors['text']}; background: transparent; border: none;")
        if reason_escaped:
            main_label.setToolTip(reason_escaped)
        row_layout.addWidget(main_label, 1, alignment=Qt.AlignVCenter)

        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        if isinstance(issue, HarperIssue):
            checkbox.setEnabled(has_edit)
            checkbox.setToolTip(t("fw.tooltip.apply_fix") if has_edit else "")
            checkbox.setStyleSheet("QCheckBox::indicator { width: 14px; height: 14px; }")
            checkbox.stateChanged.connect(lambda state, i=issue: self._on_issue_enabled_changed(i, state))
            row_layout.addWidget(checkbox, alignment=Qt.AlignVCenter)
        return row

    def _on_issue_enabled_changed(self, issue, state: int):
        if not isinstance(issue, HarperIssue):
            return
        issue.enabled = state == Qt.CheckState.Checked.value
        self._recompute_corrected_text()

    def _recompute_corrected_text(self):
        edits = []
        for issue in getattr(self, "_grammar_issues", []):
            if isinstance(issue, HarperIssue) and issue.enabled and issue.edit is not None:
                edits.append(issue.edit)
        from .harper_types import HarperFixApplier
        corrected = HarperFixApplier.apply_fixes(self._current_text, edits)
        self._rewrite_texts[0].text_edit.setPlainText(corrected)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _refresh_model_combo(self):
        if not hasattr(self, '_model_combo') or self._model_combo is None:
            return

        if self._current_mode == "optimize_translate":
            self._model_combo.hide()
            return

        # Hide model combo when in Harper (local) optimize mode
        if self._current_mode == "optimize" and config.get("general", "optimize_model") == "harper":
            self._model_combo.hide()
            return
        self._model_combo.show()

        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItem(t("fw.model.fast"), "model_1")
        self._model_combo.addItem(t("fw.model.quality"), "model_2")

        config_key = "optimize_model" if self._current_mode == "optimize" else "translate_model"
        default_val = "model_1" if self._current_mode == "optimize" else "model_2"
        current = config.get("general", config_key, default=default_val)
        idx = self._model_combo.findData(current)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        self._model_combo.blockSignals(False)

    def _on_model_combo_changed(self, idx):
        if idx < 0:
            return
        if self._current_mode == "optimize_translate":
            return
        model_type = self._model_combo.itemData(idx)
        config_key = "optimize_model" if self._current_mode == "optimize" else "translate_model"
        config.set("general", config_key, value=model_type)

    def _on_style_change(self, style_id: str):
        self._current_style = style_id
        config.set("floating_window", "last_style", value=style_id)
        for sid, btn in self._style_buttons.items():
            btn.setStyleSheet(style_btn_style(self._theme_colors, sid == style_id))
        if hasattr(self, "_combined_style_buttons"):
            for sid, btn in self._combined_style_buttons.items():
                btn.setStyleSheet(style_btn_style(self._theme_colors, sid == style_id))
        if self._current_text:
            if self._current_mode == "optimize_translate":
                self._redo_optimize_for_combined()
            elif self._current_mode == "optimize":
                self._do_optimize()

    # ---- Layout switching ----

    def _set_harper_layout(self, harper_mode: bool):
        """Toggle UI between Harper (single text) and LLM (3 rewrites) layouts."""
        if harper_mode:
            self._rewrite_texts[1].hide()
            self._rewrite_texts[2].hide()
            self._rewrite_texts[1].text_edit.clear()
            self._rewrite_texts[2].text_edit.clear()
            self._rewrite_label.setText(t("fw.label.corrected_text"))
            self._model_combo.hide()
            if hasattr(self, "_style_widget"):
                self._style_widget.hide()
            if hasattr(self, "_custom_instruction_label"):
                self._custom_instruction_label.hide()
            if hasattr(self, "_custom_entry"):
                self._custom_entry.hide()
            if hasattr(self, "_custom_btn"):
                self._custom_btn.hide()
        else:
            self._rewrite_texts[1].show()
            self._rewrite_texts[2].show()
            self._rewrite_label.setText(t("fw.label.rewrites"))
            self._model_combo.show()
            if hasattr(self, "_style_widget"):
                self._style_widget.show()
            if hasattr(self, "_custom_instruction_label"):
                self._custom_instruction_label.show()
            if hasattr(self, "_custom_entry"):
                self._custom_entry.show()
            if hasattr(self, "_custom_btn"):
                self._custom_btn.show()

    # ---- LLM calls ----

    def _do_optimize(self):
        if self._is_loading:
            return
        self._is_loading = True
        self._set_loading_state(True)

        optimize_model = config.get("general", "optimize_model", default="")

        if not optimize_model:
            self._show_toast(t("fw.toast.no_model_configured"))
            self._is_loading = False
            self._set_loading_state(False)
            return

        # ── Unified dispatch: always check Harper availability ──
        from .harper_client import HarperClient

        client = HarperClient()
        available = client.is_available()

        # ── Harper (local) branch ──
        if optimize_model == "harper" and available:
            self._set_harper_layout(True)
            MAX_HARPER_BYTES = 120 * 1024  # Harper's maxFileLength default
            if len(self._current_text.encode("utf-8")) > MAX_HARPER_BYTES:
                self._show_toast(t("harper.error.text_too_large"))
                self._is_loading = False
                self._set_loading_state(False)
                self._do_optimize_llm()
                return
            try:
                # Disconnect previous client to prevent stale callbacks
                prev = getattr(self, '_active_client', None)
                if prev is not None:
                    try:
                        prev.finished.disconnect()
                    except Exception:
                        pass  # Signal may already be disconnected; ignore.
                self._active_client = client

                # Connect to finished signal for async results
                client.finished.connect(
                    lambda result: run_on_main(
                        lambda r=result: self._on_harper_done(r)
                    )
                )
                issues, corrected_text = client.check_text(self._current_text)
                # If check_text returned actual results synchronously (test mock),
                # handle them immediately. Real HarperClient always returns ([], text).
                if issues or corrected_text != self._current_text:
                    sync_result = LintResult(
                        success=True, issues=issues, corrected_text=corrected_text
                    )
                    self._on_harper_done(sync_result)
            except Exception:
                self._show_toast(t("harper.error.process_crash"))
                self._is_loading = False
                self._do_optimize_llm()
            return

        if optimize_model == "harper" and not available:
            self._show_toast(t("harper.error.binary_not_found"))

        # ── LLM (remote) branch ──
        self._do_optimize_llm()

    def _do_optimize_llm(self):
        """Original LLM optimize flow (unchanged)."""
        self._set_harper_layout(False)
        ok, _, _, warning = check_output_fit(
            self._current_text,
            model_type=config.get("general", "optimize_model", default="model_1"),
            mode="optimize",
        )
        if not ok:
            self._show_toast(warning)
            self._is_loading = False
            self._set_loading_state(False)
            return

        style_label = FloatingWindow._get_style_label(self._current_style)

        def on_done(result, error):
            run_on_main(lambda: self._on_optimize_done(result, error))

        optimize_text(
            self._current_text,
            style=self._current_style,
            style_label=style_label,
            model_type=config.get("general", "optimize_model", default="model_1"),
            on_done=on_done,
        )

    def _on_harper_done(self, result: LintResult):
        """Callback for Harper check completion."""
        if not shiboken6.isValid(self):
            try:
                _ = self._rewrite_texts
            except RuntimeError:
                return  # C++ object already deleted

        if not result.success or result.error:
            if result.error:
                self._show_toast(result.error)
            self._is_loading = False
            self._set_loading_state(False)
            self._do_optimize_llm()
            return

        if self._rewrite_texts:
            self._rewrite_texts[0].text_edit.setPlainText(result.corrected_text)
            self._set_harper_layout(True)
            self._rewrite_texts[1].text_edit.clear()
            self._rewrite_texts[2].text_edit.clear()

        payload = {
            "grammar_issues": result.issues,
            "corrected_text": result.corrected_text,
        }
        self._on_optimize_done(payload, None)

    def _on_optimize_done(self, result, error):
        if not shiboken6.isValid(self):
            try:
                _ = self._rewrite_texts
            except RuntimeError:
                return  # C++ object already deleted
        self._is_loading = False
        self._set_loading_state(False)
        for hover_edit in self._rewrite_texts:
            hover_edit.text_edit.clear()
        if error:
            self._show_error(error)
            return
        if isinstance(result, dict):
            issues = result.get("grammar_issues", [])
            self._populate_grammar_issues(issues)

        if isinstance(result, dict) and "rewrites" in result:
            rewrites = result["rewrites"]
            for i, hover_edit in enumerate(self._rewrite_texts):
                if i < len(rewrites):
                    rw = rewrites[i]
                    content = rw.get("text", "")
                    hover_edit.text_edit.setPlainText(content)
                else:
                    hover_edit.text_edit.setPlainText(t("fw.no_more_versions"))
            if result.get("_truncated"):
                self._show_toast(t("fw.toast.truncated"))
        elif isinstance(result, dict) and "corrected_text" in result:
            self._rewrite_texts[0].text_edit.setPlainText(result["corrected_text"])
            for i in range(1, len(self._rewrite_texts)):
                self._rewrite_texts[i].text_edit.clear()
            self._set_harper_layout(True)
        else:
            self._show_raw_text(result)

    def _do_translate(self):
        if self._is_loading:
            return
        self._is_loading = True
        self._set_loading_state(True)

        translate_model = config.get("general", "translate_model", default="")

        if not translate_model:
            self._show_toast(t("fw.toast.no_model_configured"))
            self._is_loading = False
            self._set_loading_state(False)
            return

        ok, _, _, warning = check_output_fit(
            self._current_text,
            model_type=config.get("general", "translate_model", default="model_2"),
            mode="translate",
        )
        if not ok:
            self._show_toast(warning)
            self._is_loading = False
            self._set_loading_state(False)
            return

        def on_done(result, error):
            run_on_main(lambda: self._on_translate_done(result, error))

        translate_text(
            self._current_text,
            source_lang=self._source_lang.currentData(),
            target_lang=self._target_lang.currentData(),
            model_type=config.get("general", "translate_model", default="model_2"),
            on_done=on_done,
        )

    def _on_translate_done(self, result, error):
        if not shiboken6.isValid(self):
            try:
                _ = self._translation_text
            except RuntimeError:
                return  # C++ object already deleted
        self._is_loading = False
        self._set_loading_state(False)
        if error:
            self._show_error(error)
            return
        if result:
            translation = result.get("translation", "")
            self._translation_text.setPlainText(translation or t("fw.no_result"))

    def _do_optimize_translate(self):
        if self._is_loading:
            return
        self._is_loading = True

        optimize_model = config.get("general", "optimize_model", default="")
        translate_model = config.get("general", "translate_model", default="")

        if not optimize_model or not translate_model:
            self._show_toast(t("fw.label.combined_no_model"))
            self._is_loading = False
            return

        if optimize_model == "harper":
            opt_ok, opt_warning = True, ""
        else:
            opt_ok, _, _, opt_warning = check_output_fit(
                self._current_text,
                model_type=config.get("general", "optimize_model", default="model_1"),
                mode="optimize",
            )
        trans_ok, _, _, trans_warning = check_output_fit(
            self._current_text,
            model_type=config.get("general", "translate_model", default="model_2"),
            mode="translate",
        )
        if not opt_ok or not trans_ok:
            if not opt_ok:
                self._show_toast(opt_warning)
            if not trans_ok:
                self._show_toast(trans_warning)
            self._is_loading = False
            return

        self._combined_optimize_loading.show()
        self._combined_translate_loading.show()
        self._regenerate_btn.setIcon(
            qta.icon("fa5s.spinner", color=self._theme_colors["yellow"])
        )

        self._combined_pending = 2

        if optimize_model == "harper":
            self._do_optimize_translate_harper()
            return

        self._do_optimize_translate_llm()

    def _do_optimize_translate_harper(self):
        """Run Harper grammar check in parallel with LLM translation."""
        from .harper_client import HarperClient

        client = HarperClient()
        if not client.is_available():
            self._show_toast(t("harper.error.binary_not_found"))
            self._do_optimize_translate_llm()
            return

        MAX_HARPER_BYTES = 120 * 1024
        if len(self._current_text.encode("utf-8")) > MAX_HARPER_BYTES:
            self._show_toast(t("harper.error.text_too_large"))
            self._do_optimize_translate_llm()
            return

        try:
            prev = getattr(self, '_combined_active_client', None)
            if prev is not None:
                try:
                    prev.finished.disconnect()
                except RuntimeError:
                    pass  # Signal may already be disconnected; ignore.
            self._combined_active_client = client

            client.finished.connect(
                lambda result: run_on_main(
                    lambda r=result: self._on_combined_harper_done(r)
                )
            )
            issues, corrected_text = client.check_text(self._current_text)
            if issues or corrected_text != self._current_text:
                sync_result = LintResult(
                    success=True, issues=issues, corrected_text=corrected_text
                )
                self._on_combined_harper_done(sync_result)
        except (RuntimeError, OSError, ValueError):
            self._show_toast(t("harper.error.process_crash"))
            self._do_optimize_translate_llm()
            return
        except Exception as e:
            write_error(e, "FloatingWindow._do_optimize_translate_harper")
            self._show_toast(t("harper.error.process_crash"))
            self._do_optimize_translate_llm()
            return

        def on_trans_done(result, error):
            run_on_main(lambda: self._on_combined_translate_done(result, error))

        translate_text(
            self._current_text,
            source_lang=self._combined_source_lang.currentData(),
            target_lang=self._combined_target_lang.currentData(),
            model_type=config.get("general", "translate_model", default="model_2"),
            on_done=on_trans_done,
        )

    def _do_optimize_translate_llm(self):
        """Fire LLM optimize + translate in parallel for the combined tab."""
        style_label = FloatingWindow._get_style_label(self._current_style)

        def on_opt_done(result, error):
            run_on_main(lambda: self._on_combined_optimize_done(result, error))

        def on_trans_done(result, error):
            run_on_main(lambda: self._on_combined_translate_done(result, error))

        optimize_text(
            self._current_text,
            style=self._current_style,
            style_label=style_label,
            model_type=config.get("general", "optimize_model", default="model_1"),
            on_done=on_opt_done,
        )

        translate_text(
            self._current_text,
            source_lang=self._combined_source_lang.currentData(),
            target_lang=self._combined_target_lang.currentData(),
            model_type=config.get("general", "translate_model", default="model_2"),
            on_done=on_trans_done,
        )

    def _do_combined_optimize_llm_only(self):
        """Fire only LLM optimize for the combined tab (used when Harper fails)."""
        style_label = FloatingWindow._get_style_label(self._current_style)

        def on_opt_done(result, error):
            run_on_main(lambda: self._on_combined_optimize_done(result, error))

        optimize_text(
            self._current_text,
            style=self._current_style,
            style_label=style_label,
            model_type=config.get("general", "optimize_model", default="model_1"),
            on_done=on_opt_done,
        )

    def _redo_optimize_for_combined(self):
        """Re-run only the optimize side of the combined tab (e.g., after a style change)."""
        if self._is_loading:
            return
        self._is_loading = True

        optimize_model = config.get("general", "optimize_model", default="")
        if not optimize_model:
            self._show_toast(t("fw.label.combined_no_model"))
            self._is_loading = False
            return

        if optimize_model != "harper":
            ok, _, _, warning = check_output_fit(
                self._current_text,
                model_type=optimize_model,
                mode="optimize",
            )
            if not ok:
                self._show_toast(warning)
                self._is_loading = False
                return

        self._combined_optimize_loading.show()
        self._regenerate_btn.setIcon(
            qta.icon("fa5s.spinner", color=self._theme_colors["yellow"])
        )
        self._combined_pending = 1

        if optimize_model == "harper":
            self._redo_optimize_harper_for_combined()
            return

        self._do_combined_optimize_llm_only()

    def _redo_optimize_harper_for_combined(self):
        """Run Harper optimize only for the combined tab; translation is preserved."""
        from .harper_client import HarperClient

        client = HarperClient()
        if not client.is_available():
            self._show_toast(t("harper.error.binary_not_found"))
            self._do_combined_optimize_llm_only()
            return

        MAX_HARPER_BYTES = 120 * 1024
        if len(self._current_text.encode("utf-8")) > MAX_HARPER_BYTES:
            self._show_toast(t("harper.error.text_too_large"))
            self._do_combined_optimize_llm_only()
            return

        try:
            prev = getattr(self, '_combined_active_client', None)
            if prev is not None:
                try:
                    prev.finished.disconnect()
                except RuntimeError:
                    pass
            self._combined_active_client = client

            client.finished.connect(
                lambda result: run_on_main(
                    lambda r=result: self._on_combined_harper_done(r)
                )
            )
            issues, corrected_text = client.check_text(self._current_text)
            if issues or corrected_text != self._current_text:
                sync_result = LintResult(
                    success=True, issues=issues, corrected_text=corrected_text
                )
                self._on_combined_harper_done(sync_result)
        except (RuntimeError, OSError, ValueError):
            self._show_toast(t("harper.error.process_crash"))
            self._do_combined_optimize_llm_only()
        except Exception as e:
            write_error(e, "FloatingWindow._redo_optimize_harper_for_combined")
            self._show_toast(t("harper.error.process_crash"))
            self._do_combined_optimize_llm_only()

    def _on_combined_harper_done(self, result: LintResult):
        """Callback for Harper check completion in combined tab."""
        if not shiboken6.isValid(self):
            try:
                _ = self._combined_rewrite_texts
            except RuntimeError:
                return

        if not result.success or result.error:
            if result.error:
                self._show_toast(result.error)
            self._do_combined_optimize_llm_only()
            return

        self._combined_rewrite_texts[0].text_edit.setPlainText(result.corrected_text)
        self._combined_rewrite_texts[1].text_edit.clear()
        self._combined_rewrite_texts[2].text_edit.clear()
        self._combined_rewrite_texts[1].hide()
        self._combined_rewrite_texts[2].hide()
        self._populate_combined_grammar_issues(result.issues)
        self._combined_optimize_loading.hide()
        self._combined_pending -= 1
        if self._combined_pending <= 0:
            self._is_loading = False
            self._regenerate_btn.setIcon(
                qta.icon("fa5s.redo", color=self._theme_colors["text_muted"])
            )

    def _on_combined_optimize_done(self, result, error):
        if not shiboken6.isValid(self):
            try:
                _ = self._combined_rewrite_texts
            except RuntimeError:
                return
        self._combined_optimize_loading.hide()

        for hover_edit in self._combined_rewrite_texts:
            hover_edit.show()
            hover_edit.text_edit.clear()

        if error:
            for hover_edit in self._combined_rewrite_texts:
                hover_edit.text_edit.setPlainText(error)
        elif isinstance(result, dict) and "rewrites" in result:
            rewrites = result["rewrites"]
            for i, hover_edit in enumerate(self._combined_rewrite_texts):
                if i < len(rewrites):
                    rw = rewrites[i]
                    content = rw.get("text", "")
                    hover_edit.text_edit.setPlainText(content)
                else:
                    hover_edit.text_edit.setPlainText(t("fw.no_more_versions"))
            if result.get("_truncated"):
                self._show_toast(t("fw.toast.truncated"))
            issues = result.get("grammar_issues", [])
            self._populate_combined_grammar_issues(issues)
        elif isinstance(result, dict) and "corrected_text" in result:
            self._combined_rewrite_texts[0].text_edit.setPlainText(result["corrected_text"])
        else:
            self._combined_rewrite_texts[0].text_edit.setPlainText(
                result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2))

        self._combined_pending -= 1
        if self._combined_pending <= 0:
            self._is_loading = False
            self._regenerate_btn.setIcon(
                qta.icon("fa5s.redo", color=self._theme_colors["text_muted"])
            )

    def _on_combined_translate_done(self, result, error):
        if not shiboken6.isValid(self):
            try:
                _ = self._combined_translation_text
            except RuntimeError:
                return
        self._combined_translate_loading.hide()

        if error:
            self._combined_translation_text.setPlainText(error)
        elif isinstance(result, dict):
            translation = result.get("translation", "")
            self._combined_translation_text.setPlainText(translation or t("fw.no_result"))
        elif result:
            self._combined_translation_text.setPlainText(str(result))
        else:
            self._combined_translation_text.setPlainText(t("fw.no_result"))

        self._combined_pending -= 1
        if self._combined_pending <= 0:
            self._is_loading = False
            self._regenerate_btn.setIcon(
                qta.icon("fa5s.redo", color=self._theme_colors["text_muted"])
            )

    def _populate_combined_grammar_issues(self, issues: list):
        while self._combined_grammar_layout.count():
            item = self._combined_grammar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        self._combined_grammar_header.show()
        self._combined_grammar_container.show()
        self._combined_grammar_header.setText(t("fw.label.grammar_expanded"))

        if not issues:
            no_issues = QLabel(t("fw.no_issues"))
            no_issues.setStyleSheet(label_style(self._theme_colors, "green", "font-size: 12px; font-weight: 500;"))
            self._combined_grammar_layout.addWidget(no_issues)
            return

        for issue in issues:
            row = self._build_issue_row(issue)
            self._combined_grammar_layout.addWidget(row)

    def _on_custom_generate(self):
        instruction = self._custom_entry.toPlainText().strip()
        if not instruction or not self._current_text or self._is_loading:
            return
        self._is_loading = True
        self._set_loading_state(True)

        def on_done(result, error):
            run_on_main(lambda: self._on_custom_done(result, error))

        custom_instruction(
            self._current_text, instruction,
            model_type=config.get("general", "optimize_model", default="model_1"),
            on_done=on_done,
        )

    def _on_custom_done(self, result, error):
        if not shiboken6.isValid(self):
            try:
                _ = self._rewrite_texts
            except RuntimeError:
                return  # C++ object already deleted
        self._is_loading = False
        self._set_loading_state(False)
        if error:
            self._show_error(error)
            return
        text = ""
        if result and "result" in result:
            text = result["result"]
        if text:
            self._rewrite_texts[0].text_edit.setPlainText(text)

    def _on_regenerate(self):
        if self._current_mode == "translate":
            self._do_translate()
        elif self._current_mode == "optimize_translate":
            self._do_optimize_translate()
        else:
            self._do_optimize()

    def _on_settings(self):
        from .settings_panel import SettingsPanel
        dlg = SettingsPanel(self)
        dlg.exec()

    def _do_replace(self, text: str):
        if not text or not text.strip():
            return
        try:
            self._grabber.focus_foreground()
            success = self._grabber.replace_text(text)
        except Exception as e:
            write_error(e, "FloatingWindow._do_replace")
            success = False
        if success:
            self._show_toast(t("fw.toast.replaced"))
            if config.get("general", "replace_auto_close", default=False):
                self._close()
        else:
            self._show_toast(t("fw.toast.replace_failed"))

    def _on_copy_text(self, textbox):
        QApplication.clipboard().setText(textbox.toPlainText())
        self._show_toast(t("fw.toast.copied"))

    def _show_toast(self, message: str):
        toast = QLabel(message, self)
        toast.setStyleSheet(toast_style(self._theme_colors))
        toast.setAttribute(Qt.WA_DeleteOnClose, True)
        toast.adjustSize()
        toast.move((self.width() - toast.width()) // 2, self.height() - 40)
        toast.show()
        QTimer.singleShot(1500, lambda: toast.close() if shiboken6.isValid(toast) else None)

    def _show_error(self, message: str):
        for hover_edit in self._rewrite_texts:
            hover_edit.text_edit.setPlainText(message)

    def _show_raw_text(self, result):
        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2)
        self._rewrite_texts[0].text_edit.setPlainText(content)

    def _set_loading_state(self, loading: bool):
        if loading:
            self._regenerate_btn.setIcon(qta.icon("fa5s.spinner", color=self._theme_colors["yellow"]))
        else:
            self._regenerate_btn.setIcon(qta.icon("fa5s.redo", color=self._theme_colors["text_muted"]))
        if loading:
            self._loading_overlay.show()
            self._loading_overlay.raise_()
        else:
            self._loading_overlay.hide()

    def _toggle_pin(self):
        self._pinned = not self._pinned
        flags = self.windowFlags()
        if self._pinned:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        pin_color = self._theme_colors["text_muted"] if self._pinned else self._theme_colors["surface_hover"]
        self._pin_btn.setIcon(qta.icon("fa5s.thumbtack", color=pin_color))
        self.show()

    def _retranslate_ui(self):
        """Re-apply translations when language changes."""
        if hasattr(self, '_title_label'):
            self._title_label.setText(t("fw.title"))
        if hasattr(self, '_tabs'):
            self._tabs.setTabText(0, t("fw.tab.optimize"))
            self._tabs.setTabText(1, t("fw.tab.translate"))
            self._tabs.setTabText(2, t("fw.tab.optimize_translate"))
        if hasattr(self, '_style_label'):
            self._style_label.setText(t("fw.label.style"))
        if hasattr(self, '_style_buttons'):
            styles = config.get("styles", default=[])
            style_by_id = {s["id"]: s for s in styles}
            for sid, btn in self._style_buttons.items():
                label = t(f"style.{sid}")
                if label == f"style.{sid}":
                    s = style_by_id.get(sid, {})
                    label = s.get("label", sid)
                btn.setText(label)
        if hasattr(self, '_model_combo') and self._model_combo is not None:
            self._model_combo.blockSignals(True)
            current_data = self._model_combo.currentData()
            self._model_combo.clear()
            self._model_combo.addItem(t("fw.model.fast"), "model_1")
            self._model_combo.addItem(t("fw.model.quality"), "model_2")
            if current_data:
                idx = self._model_combo.findData(current_data)
                if idx >= 0:
                    self._model_combo.setCurrentIndex(idx)
            self._model_combo.blockSignals(False)

        # Retranslate combined tab widgets
        if hasattr(self, '_combined_optimize_label'):
            self._combined_optimize_label.setText(t("fw.label.optimize_section"))
        if hasattr(self, '_combined_translate_label'):
            self._combined_translate_label.setText(t("fw.label.translate_section"))
        if hasattr(self, '_combined_style_label'):
            self._combined_style_label.setText(t("fw.label.style"))
        if hasattr(self, '_combined_style_buttons'):
            styles = config.get("styles", default=[])
            style_by_id = {s["id"]: s for s in styles}
            for sid, btn in self._combined_style_buttons.items():
                label = t(f"style.{sid}")
                if label == f"style.{sid}":
                    s = style_by_id.get(sid, {})
                    label = s.get("label", sid)
                btn.setText(label)
        if hasattr(self, '_combined_grammar_header'):
            self._combined_grammar_header.setText(t("fw.label.grammar_expanded"))
        if hasattr(self, '_combined_rewrite_label'):
            self._combined_rewrite_label.setText(t("fw.label.rewrites"))
        if hasattr(self, '_combined_source_lang_label'):
            self._combined_source_lang_label.setText(t("fw.label.source_lang"))
        if hasattr(self, '_combined_target_lang_label'):
            self._combined_target_lang_label.setText(t("fw.label.target_lang"))
        if hasattr(self, '_combined_translation_result_label'):
            self._combined_translation_result_label.setText(t("fw.label.translation_result"))
        if hasattr(self, '_combined_trans_replace_btn'):
            self._combined_trans_replace_btn.setText(t("fw.btn.replace_original"))
        if hasattr(self, '_combined_trans_copy_btn'):
            self._combined_trans_copy_btn.setText(t("fw.btn.copy"))

    def _apply_theme(self, name: str):
        tc = get_theme(name)["colors"]
        self._theme_colors = tc
        self._bg_color = QColor(tc["bg"])
        self._border_color = QColor(tc["border"])

        self._drag_bar.setStyleSheet(titlebar_style(tc, self._radius))
        self._settings_btn.setIcon(qta.icon("fa5s.cog", color=tc["text_muted"]))
        self._settings_btn.setStyleSheet(btn_style(tc))
        self._min_btn.setIcon(qta.icon("fa5s.window-minimize", color=tc["text_muted"]))
        self._min_btn.setStyleSheet(btn_style(tc))
        self._close_btn.setIcon(qta.icon("fa5s.times", color=tc["red"]))
        self._close_btn.setStyleSheet(btn_style(tc, "red"))
        self._regenerate_btn.setIcon(qta.icon("fa5s.redo", color=tc["text_muted"]))
        self._regenerate_btn.setStyleSheet(btn_style(tc))
        self._title_label.setStyleSheet(label_style(tc, "text", "font-weight: 600; font-size: 13px;"))

        self._tabs.setStyleSheet(tab_style(tc))
        if self._model_combo is not None:
            self._model_combo.setStyleSheet(combo_style(tc))

        self._optimize_scroll.setStyleSheet(scroll_area_style(tc))
        self._style_label.setStyleSheet(label_style(tc, "text_muted", "font-size: 12px; font-weight: 500;"))
        active_sid = self._current_style
        for sid, btn in self._style_buttons.items():
            btn.setStyleSheet(style_btn_style(tc, sid == active_sid))
        self._grammar_header.setStyleSheet(label_style(tc, "text_muted", "font-size: 13px; font-weight: 600; margin-top: 6px;"))
        if hasattr(self, '_custom_entry') and self._custom_entry is not None:
            self._custom_entry.setStyleSheet(text_edit_style(tc))
        if hasattr(self, '_custom_btn') and self._custom_btn is not None:
            self._custom_btn.setStyleSheet(action_btn_style(tc, "surface"))

        self._translate_scroll.setStyleSheet(scroll_area_style(tc))
        self._source_lang.setStyleSheet(combo_style(tc))
        self._target_lang.setStyleSheet(combo_style(tc))
        self._translation_text.setStyleSheet(text_edit_style(tc))
        self._trans_replace_btn.setStyleSheet(action_btn_style(tc, "accent"))
        self._trans_copy_btn.setStyleSheet(action_btn_style(tc, "surface"))

        # Style combined tab widgets
        if hasattr(self, '_combined_scroll') and self._combined_scroll is not None:
            self._combined_scroll.setStyleSheet(scroll_area_style(tc))
        if hasattr(self, '_combined_optimize_label') and self._combined_optimize_label is not None:
            self._combined_optimize_label.setStyleSheet(
                label_style(tc, "text", "font-size: 13px; font-weight: 600;"))
        if hasattr(self, '_combined_translate_label') and self._combined_translate_label is not None:
            self._combined_translate_label.setStyleSheet(
                label_style(tc, "text", "font-size: 13px; font-weight: 600;"))
        if hasattr(self, '_combined_style_label') and self._combined_style_label is not None:
            self._combined_style_label.setStyleSheet(
                label_style(tc, "text_muted", "font-size: 12px; font-weight: 500;"))
        if hasattr(self, '_combined_style_buttons'):
            active_sid = self._current_style
            for sid, btn in self._combined_style_buttons.items():
                btn.setStyleSheet(style_btn_style(tc, sid == active_sid))
        if hasattr(self, '_combined_grammar_header') and self._combined_grammar_header is not None:
            self._combined_grammar_header.setStyleSheet(
                label_style(tc, "text_muted", "font-size: 13px; font-weight: 600; margin-top: 6px;"))
        if hasattr(self, '_combined_rewrite_label') and self._combined_rewrite_label is not None:
            self._combined_rewrite_label.setStyleSheet(
                label_style(tc, "text_muted", "font-size: 12px; font-weight: 500;"))
        if hasattr(self, '_combined_rewrite_texts'):
            for he in self._combined_rewrite_texts:
                he.update_theme(tc)
        if hasattr(self, '_combined_source_lang') and self._combined_source_lang is not None:
            self._combined_source_lang.setStyleSheet(combo_style(tc))
        if hasattr(self, '_combined_target_lang') and self._combined_target_lang is not None:
            self._combined_target_lang.setStyleSheet(combo_style(tc))
        if hasattr(self, '_combined_translation_text') and self._combined_translation_text is not None:
            self._combined_translation_text.setStyleSheet(text_edit_style(tc))
        if hasattr(self, '_combined_trans_replace_btn') and self._combined_trans_replace_btn is not None:
            self._combined_trans_replace_btn.setStyleSheet(action_btn_style(tc, "accent"))
        if hasattr(self, '_combined_trans_copy_btn') and self._combined_trans_copy_btn is not None:
            self._combined_trans_copy_btn.setStyleSheet(action_btn_style(tc, "surface"))
        if hasattr(self, '_combined_source_lang_label') and self._combined_source_lang_label is not None:
            self._combined_source_lang_label.setStyleSheet(
                label_style(tc, "text_muted", "font-size: 12px; font-weight: 500;"))
        if hasattr(self, '_combined_target_lang_label') and self._combined_target_lang_label is not None:
            self._combined_target_lang_label.setStyleSheet(
                label_style(tc, "text_muted", "font-size: 12px; font-weight: 500;"))
        if hasattr(self, '_combined_translation_result_label') and self._combined_translation_result_label is not None:
            self._combined_translation_result_label.setStyleSheet(
                label_style(tc, "text_muted", "font-size: 12px; font-weight: 500;"))

        self._loading_overlay.setStyleSheet(
            f"background: {rgba(tc['bg'], 200)}; border-radius: 8px;")
        self._loading_label.setStyleSheet(
            label_style(tc, "text", "font-size: 16px; font-weight: 600; border: none;"))

        for he in self._rewrite_texts:
            he.update_theme(tc)

        pin_color = tc["text_muted"] if self._pinned else tc["surface_hover"]
        self._pin_btn.setIcon(qta.icon("fa5s.thumbtack", color=pin_color))
        self._pin_btn.setStyleSheet(btn_style(tc))

        self.update()

    def _close(self):
        self._save_geometry()
        # Release mouse grab if DragBar is mid-drag to avoid permanent global grab
        if hasattr(self, '_drag_bar') and self._drag_bar._dragging:
            self._drag_bar.releaseMouse()
            self._drag_bar._dragging = False
        self.hide()
        if self._on_close:
            self._on_close()

    def _save_geometry(self):
        config.update_section("floating_window", {
            "position_x": self.x(),
            "position_y": self.y(),
            "width": self.width(),
            "height": self.height(),
        })

    def cleanup(self):
        remove_listener(self._retranslate_ui)
        try:
            self._save_geometry()
        except Exception as e:
            write_error(e, "FloatingWindow.cleanup:save_geometry")
            pass
        try:
            self.hide()
        except Exception as e:
            write_error(e, "FloatingWindow.cleanup:hide")
            pass
        super().deleteLater()

    # ---- Styles ----

    @staticmethod
    def _auto_resize_text_edit(text_edit: QTextEdit):
        doc = text_edit.document()
        doc.setDocumentMargin(2)
        doc_height = doc.size().height()
        margins = text_edit.contentsMargins()
        frame = text_edit.frameWidth() * 2
        total = doc_height + margins.top() + margins.bottom() + frame + 8
        new_height = max(80, min(300, int(total)))
        if abs(new_height - text_edit.height()) > 2:
            text_edit.setFixedHeight(new_height)

    @staticmethod
    def _get_style_label(style_id: str) -> str:
        styles = config.get("styles", default=[])
        for s in styles:
            if s["id"] == style_id:
                label = t(f"style.{style_id}")
                if label == f"style.{style_id}":
                    label = s.get("label", style_id)
                return label
        return style_id

    # ---- PySide compatibility aliases for main.py ----

    def deiconify(self):
        self.show()
        QApplication.processEvents()
        self.raise_()

    def withdraw(self):
        self.hide()

    def lift_widget(self):
        self.raise_()

    def focus_force(self):
        self.activateWindow()

    def winfo_exists(self):
        return self.isVisible()

    def winfo_viewable(self):
        return self.isVisible()

    def after(self, ms: int, callback: Callable):
        QTimer.singleShot(ms, callback)

    def process_events(self):
        QApplication.processEvents()

    lift = lift_widget
