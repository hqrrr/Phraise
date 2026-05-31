from .config import config
from .dispatch import run_on_main
from .error_log import write_error
from .i18n import t, SOURCE_LANGUAGES, TARGET_LANGUAGES, add_listener, remove_listener
from .llm_client import optimize_text, translate_text, custom_instruction, check_output_fit
from .text_grabber import TextGrabber
from .theme import (
    DEFAULT_THEME as theme,
    btn_style, action_btn_style, style_btn_style,
    combo_style, tab_style, entry_style, text_edit_style,
    card_style, titlebar_style, scroll_area_style,
    label_style, separator_style, toast_style, rgba,
)

import html
import json
import threading
from collections.abc import Callable

import qtawesome as qta

from PySide6.QtCore import Qt, QPoint, QRect, QSize, QTimer
from PySide6.QtGui import QFont, QColor, QMouseEvent, QPainter, QPainterPath, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTabWidget, QScrollArea, QTextEdit, QComboBox,
    QFrame, QSizePolicy, QGridLayout, QLayout
)


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

    def __del__(self):
        while self.count():
            self.takeAt(0)

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


class _HoverTextEdit(QWidget):
    """Text edit with hover-reveal action buttons (replace / copy)."""

    def __init__(self, parent, on_replace, on_copy):
        super().__init__(parent)
        self.setMouseTracking(True)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMinimumHeight(80)
        self.text_edit.setMaximumHeight(300)
        self.text_edit.setFixedHeight(100)
        self.text_edit.setStyleSheet(text_edit_style(theme))
        self.text_edit.setMouseTracking(True)

        self._btn_overlay = QWidget(self)
        self._btn_overlay.setStyleSheet(
            f"background: {rgba(theme['surface'], 220)}; border-radius: 4px; padding: 2px;")
        self._btn_overlay.setMouseTracking(True)
        btn_layout = QHBoxLayout(self._btn_overlay)
        btn_layout.setContentsMargins(4, 2, 4, 2)
        btn_layout.setSpacing(4)

        self._replace_btn = QPushButton(t("fw.btn.replace"))
        self._replace_btn.setFixedSize(80, 22)
        self._replace_btn.setStyleSheet(action_btn_style(theme, "#6c5ce7"))
        self._replace_btn.clicked.connect(lambda: on_replace(self.text_edit.toPlainText()))
        btn_layout.addWidget(self._replace_btn)

        copy_btn = QPushButton(t("fw.btn.copy"))
        copy_btn.setFixedSize(48, 22)
        copy_btn.setStyleSheet(action_btn_style(theme, "#45475a"))
        copy_btn.clicked.connect(lambda: on_copy(self.text_edit))
        btn_layout.addWidget(copy_btn)

        self._btn_overlay.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_edit)

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


class FloatingWindow(QWidget):
    """Main floating window with optimize and translate tabs."""

    def __init__(self, grabber: TextGrabber, on_close: Callable | None = None):
        super().__init__()
        self._on_close = on_close
        self._grabber = grabber
        self._current_text: str = ""
        self._current_mode: str = "optimize"
        self._current_style: str = config.get("floating_window", "last_style", default="concise")
        self._is_loading: bool = False
        self._pinned: bool = True
        self._model_combo = None

        self._setup_window()
        self._build_ui()

        add_listener(self._retranslate_ui)

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
        self.setMaximumSize(700, 800)

        self._radius = 12
        self._bg_color = QColor(theme["bg"])
        self._border_color = QColor(theme["border"])
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
        grip_color = QColor(theme["text_muted"])
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
        if mode == "translate":
            self._tabs.setCurrentIndex(1)
            self._do_translate()
        else:
            self._tabs.setCurrentIndex(0)
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
            f"background: {theme['bg_darker']}; border-bottom: 1px solid {theme['border']};"
            f"border-bottom-left-radius: {self._radius}px;"
            f"border-bottom-right-radius: {self._radius}px;")
        main_layout.addWidget(footer)

        self._loading_overlay = QWidget(self)
        self._loading_overlay.setStyleSheet(
            f"background: {rgba(theme['bg'], 200)}; border-radius: 8px;")
        self._loading_overlay.hide()
        overlay_layout = QVBoxLayout(self._loading_overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)
        self._loading_label = QLabel(f"\u23f3 {t('fw.loading')}")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setStyleSheet(label_style(theme, "text", "font-size: 16px; font-weight: 600; border: none;"))
        overlay_layout.addWidget(self._loading_label)

    def _build_titlebar(self, layout: QVBoxLayout):
        bar = _DragBar(self, self._titlebar_height)
        bar.setStyleSheet(titlebar_style(theme, self._radius))
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 0, 4, 0)

        title = QLabel("PhrAIse")
        title.setStyleSheet(label_style(theme, "text", "font-weight: 600; font-size: 13px;"))
        bar_layout.addWidget(title)
        bar_layout.addStretch()

        regen_btn = QPushButton()
        regen_btn.setFixedSize(32, 28)
        regen_btn.setIcon(qta.icon("fa5s.redo", color=theme["text_muted"]))
        regen_btn.setIconSize(regen_btn.size() * 0.5)
        regen_btn.setStyleSheet(btn_style(theme))
        regen_btn.clicked.connect(self._on_regenerate)
        bar_layout.addWidget(regen_btn)
        self._regenerate_btn = regen_btn

        settings_btn = QPushButton()
        settings_btn.setFixedSize(32, 28)
        settings_btn.setIcon(qta.icon("fa5s.cog", color=theme["text_muted"]))
        settings_btn.setIconSize(settings_btn.size() * 0.55)
        settings_btn.setStyleSheet(btn_style(theme))
        settings_btn.clicked.connect(self._on_settings)
        bar_layout.addWidget(settings_btn)

        pin_btn = QPushButton()
        pin_btn.setFixedSize(32, 28)
        pin_btn.setIcon(qta.icon("fa5s.thumbtack", color=theme["text_muted"]))
        pin_btn.setIconSize(pin_btn.size() * 0.55)
        pin_btn.setStyleSheet(btn_style(theme))
        pin_btn.clicked.connect(self._toggle_pin)
        bar_layout.addWidget(pin_btn)

        min_btn = QPushButton()
        min_btn.setFixedSize(32, 28)
        min_btn.setIcon(qta.icon("fa5s.window-minimize", color=theme["text_muted"]))
        min_btn.setIconSize(min_btn.size() * 0.45)
        min_btn.setStyleSheet(btn_style(theme))
        min_btn.clicked.connect(self._close)
        bar_layout.addWidget(min_btn)

        close_btn = QPushButton()
        close_btn.setFixedSize(32, 28)
        close_btn.setIcon(qta.icon("fa5s.times", color=theme["red"]))
        close_btn.setIconSize(close_btn.size() * 0.55)
        close_btn.setStyleSheet(btn_style(theme, "#f38ba8"))
        close_btn.clicked.connect(self._close)
        bar_layout.addWidget(close_btn)
        self._pin_btn = pin_btn

        layout.addWidget(bar)

    def _build_tabs(self, layout: QVBoxLayout):
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(tab_style(theme))
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._build_optimize_tab()
        self._build_translate_tab()

        corner = QWidget()
        corner.setFixedSize(148, 30)
        self._model_combo = NoScrollComboBox(corner)
        self._model_combo.setFixedWidth(140)
        self._model_combo.move(4, 2)
        self._model_combo.setStyleSheet(combo_style(theme))
        self._model_combo.currentIndexChanged.connect(self._on_model_combo_changed)
        self._refresh_model_combo()
        self._tabs.setCornerWidget(corner, Qt.TopRightCorner)

        layout.addWidget(self._tabs, 1)

    def _build_optimize_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scroll_area_style(theme))

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        styles = config.get("styles", default=[])
        style_widget = QWidget()
        style_layout = FlowLayout(style_widget, spacing=4)
        style_layout.setContentsMargins(0, 0, 0, 0)
        self._style_label = QLabel(t("fw.label.style"))
        self._style_label.setStyleSheet(label_style(theme, "text_muted", "font-size: 12px; font-weight: 500;"))
        style_layout.addWidget(self._style_label)
        self._style_buttons: dict[str, QPushButton] = {}
        for s in styles:
            btn = QPushButton(s.get("label", s["id"]))
            btn.setFixedSize(80, 26)
            sid = s["id"]
            active = sid == self._current_style
            btn.setStyleSheet(style_btn_style(theme, active))
            btn.clicked.connect(lambda checked, sid=sid: self._on_style_change(sid))
            style_layout.addWidget(btn)
            self._style_buttons[sid] = btn
        layout.addWidget(style_widget)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(separator_style(theme))
        layout.addWidget(sep)

        # Grammar issues section
        self._grammar_header = QLabel(t("fw.label.grammar_expanded"))
        self._grammar_header.setStyleSheet(label_style(theme, "text_muted", "font-size: 13px; font-weight: 600; margin-top: 6px;"))
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
            hover_edit = _HoverTextEdit(container, self._do_replace, self._on_copy_text)
            hover_edit.text_edit.textChanged.connect(
                lambda he=hover_edit: FloatingWindow._auto_resize_text_edit(he.text_edit))
            layout.addWidget(hover_edit)
            self._rewrite_texts.append(hover_edit)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(separator_style(theme))
        layout.addWidget(sep2)

        self._custom_instruction_label = QLabel(t("fw.label.custom_instruction"))
        layout.addWidget(self._custom_instruction_label)
        self._custom_entry = QTextEdit()
        self._custom_entry.setMinimumHeight(40)
        self._custom_entry.setMaximumHeight(120)
        self._custom_entry.setFixedHeight(40)
        self._custom_entry.setStyleSheet(text_edit_style(theme))
        self._custom_entry.textChanged.connect(lambda: FloatingWindow._auto_resize_text_edit(self._custom_entry))
        layout.addWidget(self._custom_entry)

        self._custom_btn = QPushButton(t("fw.btn.generate"))
        self._custom_btn.setFixedSize(80, 26)
        self._custom_btn.setStyleSheet(action_btn_style(theme, "#45475a"))
        self._custom_btn.clicked.connect(self._on_custom_generate)
        layout.addWidget(self._custom_btn)
        layout.addStretch()

        scroll.setWidget(container)
        self._tabs.addTab(scroll, t("fw.tab.optimize"))

    def _build_translate_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scroll_area_style(theme))

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
        self._source_lang.setStyleSheet(combo_style(theme))
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
        self._target_lang.setStyleSheet(combo_style(theme))
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
        sep.setStyleSheet(separator_style(theme))
        layout.addWidget(sep)

        self._translation_result_label = QLabel(t("fw.label.translation_result"))
        layout.addWidget(self._translation_result_label)
        self._translation_text = QTextEdit()
        self._translation_text.setReadOnly(True)
        self._translation_text.setMinimumHeight(60)
        self._translation_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._translation_text.setStyleSheet(text_edit_style(theme))
        layout.addWidget(self._translation_text, 1)

        trans_btn_row = QWidget()
        trans_btn_layout = QHBoxLayout(trans_btn_row)
        trans_btn_layout.setContentsMargins(0, 4, 0, 0)
        self._trans_replace_btn = QPushButton(t("fw.btn.replace_original"))
        self._trans_replace_btn.setFixedSize(130, 24)
        self._trans_replace_btn.setStyleSheet(action_btn_style(theme, "#6c5ce7"))
        self._trans_replace_btn.clicked.connect(lambda checked=False: self._do_replace(self._translation_text.toPlainText()))
        trans_btn_layout.addWidget(self._trans_replace_btn)
        self._trans_copy_btn = QPushButton(t("fw.btn.copy"))
        self._trans_copy_btn.setFixedSize(50, 24)
        self._trans_copy_btn.setStyleSheet(action_btn_style(theme, "#45475a"))
        self._trans_copy_btn.clicked.connect(lambda checked=False: self._on_copy_text(self._translation_text))
        trans_btn_layout.addWidget(self._trans_copy_btn)
        trans_btn_layout.addStretch()
        layout.addWidget(trans_btn_row)

        scroll.setWidget(container)
        self._tabs.addTab(scroll, t("fw.tab.translate"))

    # ---- Event handlers ----

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            return
        edge = self._get_resize_edge(event.position().toPoint())
        if edge:
            self._resizing = True
            self._resize_edge = edge
            self._drag_start = event.globalPosition().toPoint()
            self._drag_start_geo = QRect(self.geometry())
        else:
            self._resizing = False
            self._resize_edge = ""

    def mouseMoveEvent(self, event: QMouseEvent):
        gpos = event.globalPosition().toPoint()
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
        else:
            edge = self._get_resize_edge(event.position().toPoint())
            if "e" in edge and "s" in edge:
                self.setCursor(Qt.SizeFDiagCursor)
            elif "w" in edge and "n" in edge:
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

    def mouseReleaseEvent(self, event: QMouseEvent):
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

    # ---- Tab & style ----

    def _on_tab_changed(self, idx):
        self._current_mode = "optimize" if idx == 0 else "translate"
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

        if not issues:
            no_issues = QLabel(t("fw.no_issues"))
            no_issues.setStyleSheet(label_style(theme, "green", "font-size: 12px; font-weight: 500;"))
            self._grammar_layout.addWidget(no_issues)
            return

        for issue in issues:
            original = html.escape(issue.get("original", ""))
            suggestion = html.escape(issue.get("suggestion", ""))
            reason = issue.get("reason", "")
            severity = issue.get("severity", "warning")

            badge_color = theme["red"] if severity == "error" else theme["orange"]
            escaped_reason = html.escape(reason) if reason else ""

            rich_text = (
                f"<span style='color:{badge_color};font-size:13px;'>●</span> "
                f"<s style='color:{theme['red']};'>{original}</s> "
                f"<span style='color:{theme['green']};'>→ {suggestion}</span>"
            )
            if escaped_reason:
                rich_text += (
                    f"<br><span style='color:{theme['text_dim']};font-size:10px;'>"
                    f"{escaped_reason}</span>"
                )

            label = QLabel(rich_text)
            label.setWordWrap(True)
            label.setTextFormat(Qt.RichText)
            label.setStyleSheet(
                f"background: {theme['surface']}; border: 1px solid {theme['border']}; "
                f"border-radius: 6px; padding: 6px 8px; font-size: 12px; color: {theme['text']};")
            self._grammar_layout.addWidget(label)

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
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItem("Fast", "model_1")
        self._model_combo.addItem("Quality", "model_2")

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
        model_type = self._model_combo.itemData(idx)
        config_key = "optimize_model" if self._current_mode == "optimize" else "translate_model"
        config.set("general", config_key, value=model_type)

    def _on_style_change(self, style_id: str):
        self._current_style = style_id
        config.set("floating_window", "last_style", value=style_id)
        for sid, btn in self._style_buttons.items():
            btn.setStyleSheet(style_btn_style(theme, sid == style_id))
        if self._current_text:
            self._do_optimize()

    # ---- LLM calls ----

    def _do_optimize(self):
        if self._is_loading:
            return
        self._is_loading = True
        self._set_loading_state(True)

        ok, _, _, warning = check_output_fit(
            self._current_text,
            model_type=config.get("general", "optimize_model", default="model_1"),
            mode="optimize",
        )
        if not ok:
            self._show_toast(warning)

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

    def _on_optimize_done(self, result, error):
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
        else:
            self._show_raw_text(result)

    def _do_translate(self):
        if self._is_loading:
            return
        self._is_loading = True
        self._set_loading_state(True)

        ok, _, _, warning = check_output_fit(
            self._current_text,
            model_type=config.get("general", "translate_model", default="model_2"),
            mode="translate",
        )
        if not ok:
            self._show_toast(warning)

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
        self._is_loading = False
        self._set_loading_state(False)
        if error:
            self._show_error(error)
            return
        if result:
            translation = result.get("translation", "")
            self._translation_text.setPlainText(translation or t("fw.no_result"))

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
        toast.setStyleSheet(toast_style(theme))
        toast.adjustSize()
        toast.move((self.width() - toast.width()) // 2, self.height() - 40)
        toast.show()
        QTimer.singleShot(1500, toast.deleteLater)

    def _show_error(self, message: str):
        for hover_edit in self._rewrite_texts:
            hover_edit.text_edit.setPlainText(message)

    def _show_raw_text(self, result):
        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2)
        self._rewrite_texts[0].text_edit.setPlainText(content)

    def _set_loading_state(self, loading: bool):
        if loading:
            self._regenerate_btn.setIcon(qta.icon("fa5s.spinner", color=theme["yellow"]))
        else:
            self._regenerate_btn.setIcon(qta.icon("fa5s.redo", color=theme["text_muted"]))
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
        pin_color = theme["text_muted"] if self._pinned else theme["surface_hover"]
        self._pin_btn.setIcon(qta.icon("fa5s.thumbtack", color=pin_color))
        self.show()

    def _retranslate_ui(self):
        """Re-apply translations when language changes."""
        if hasattr(self, '_tabs'):
            self._tabs.setTabText(0, t("fw.tab.optimize"))
            self._tabs.setTabText(1, t("fw.tab.translate"))

    def _close(self):
        self._save_geometry()
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

    def destroy(self):
        remove_listener(self._retranslate_ui)
        try:
            self._save_geometry()
        except Exception as e:
            write_error(e, "FloatingWindow.destroy:save_geometry")
            pass
        try:
            self.hide()
        except Exception as e:
            write_error(e, "FloatingWindow.destroy:hide")
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
                return s.get("label", style_id)
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

    def update(self):
        QApplication.processEvents()

    lift = lift_widget
