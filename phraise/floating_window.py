from .config import config
from .dispatch import run_on_main
from .error_log import write_error
from .llm_client import optimize_text, translate_text, custom_instruction
from .text_grabber import TextGrabber

import html
import json
import threading
from collections.abc import Callable

from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtGui import QFont, QColor, QMouseEvent, QPainter, QPainterPath, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTabWidget, QScrollArea, QTextEdit, QComboBox,
    QFrame, QSizePolicy, QGridLayout,
)


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


class FloatingWindow(QWidget):
    """Main floating window with optimize and translate tabs."""

    def __init__(self, on_close: Callable | None = None):
        super().__init__()
        self._on_close = on_close
        self._grabber = TextGrabber()
        self._current_text: str = ""
        self._current_mode: str = "optimize"
        self._current_style: str = config.get("floating_window", "last_style", default="concise")
        self._is_loading: bool = False
        self._pinned: bool = True
        self._model_combo = None

        self._setup_window()
        self._build_ui()

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowOpacity(config.get("floating_window", "opacity", default=0.95))

        w = config.get("floating_window", "width", default=400)
        h = config.get("floating_window", "height", default=500)
        x = config.get("floating_window", "position_x", default=1400)
        y = config.get("floating_window", "position_y", default=600)
        self.setGeometry(x, y, w, h)
        self.setMinimumSize(350, 380)
        self.setMaximumSize(700, 800)

        self._radius = 12
        self._bg_color = QColor("#1e1e2e")
        self._border_color = QColor("#45475a")
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
        self._build_bottom_bar(main_layout)

    def _build_titlebar(self, layout: QVBoxLayout):
        bar = _DragBar(self, self._titlebar_height)
        bar.setStyleSheet(f"""
            background: #181825; border-top-left-radius: {self._radius}px;
            border-top-right-radius: {self._radius}px;
        """)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 0, 4, 0)

        title = QLabel("PhrAIse")
        title.setStyleSheet("color: #cdd6f4; font-weight: 600; font-size: 13px; background: transparent;")
        bar_layout.addWidget(title)
        bar_layout.addStretch()

        pin_btn = QPushButton("\U0001f4cc")
        pin_btn.setFixedSize(32, 28)
        pin_btn.setStyleSheet(self._btn_style())
        pin_btn.clicked.connect(self._toggle_pin)
        bar_layout.addWidget(pin_btn)

        min_btn = QPushButton("_")
        min_btn.setFixedSize(32, 28)
        min_btn.setStyleSheet(self._btn_style())
        min_btn.clicked.connect(self._close)
        bar_layout.addWidget(min_btn)

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(32, 28)
        close_btn.setStyleSheet(self._btn_style("#f38ba8"))
        close_btn.clicked.connect(self._close)
        bar_layout.addWidget(close_btn)
        self._pin_btn = pin_btn

        layout.addWidget(bar)

    def _build_tabs(self, layout: QVBoxLayout):
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: #1e1e2e; }}
            QTabBar::tab {{ background: #313244; color: #a6adc8; padding: 8px 20px;
                           border: none; font-size: 13px; font-weight: 500; }}
            QTabBar::tab:selected {{ background: #6c5ce7; color: #fff; }}
            QTabBar::tab:hover:!selected {{ background: #45475a; }}
        """)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._build_optimize_tab()
        self._build_translate_tab()

        layout.addWidget(self._tabs, 1)

    def _build_optimize_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        styles = config.get("styles", default=[])
        style_widget = QWidget()
        style_layout = QHBoxLayout(style_widget)
        style_layout.setContentsMargins(0, 0, 0, 0)
        style_label = QLabel("风格：")
        style_label.setStyleSheet("color: #a6adc8; font-size: 12px; font-weight: 500;")
        style_layout.addWidget(style_label)
        self._style_buttons: dict[str, QPushButton] = {}
        for s in styles:
            btn = QPushButton(s.get("label", s["id"]))
            btn.setFixedSize(60, 26)
            sid = s["id"]
            active = sid == self._current_style
            btn.setStyleSheet(self._style_btn_style(active))
            btn.clicked.connect(lambda checked, sid=sid: self._on_style_change(sid))
            style_layout.addWidget(btn)
            self._style_buttons[sid] = btn
        style_layout.addStretch()
        layout.addWidget(style_widget)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #45475a;")
        layout.addWidget(sep)

        # Grammar issues section
        self._grammar_header = QLabel("语法检查 ▼")
        self._grammar_header.setStyleSheet("color: #a6adc8; font-size: 13px; font-weight: 600; margin-top: 6px;")
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

        layout.addWidget(QLabel("改写版本："))
        self._rewrite_texts: list[QTextEdit] = []
        self._rewrite_replace_btns: list[QPushButton] = []
        self._rewrite_copy_btns: list[QPushButton] = []
        for i in range(3):
            frame = QFrame()
            frame.setStyleSheet("QFrame { background: #313244; border-radius: 10px; border: 1px solid #45475a; }")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(6, 6, 6, 2)

            textbox = QTextEdit()
            textbox.setReadOnly(True)
            textbox.setFixedHeight(100)
            textbox.setStyleSheet("QTextEdit { background: #181825; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; font-size: 12px; padding: 4px; }")
            frame_layout.addWidget(textbox)

            btn_row = QWidget()
            btn_layout = QHBoxLayout(btn_row)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            replace_btn = QPushButton("替换")
            replace_btn.setFixedSize(50, 24)
            replace_btn.setStyleSheet(self._action_btn_style("#6c5ce7"))
            replace_btn.clicked.connect(lambda checked=False, tb=textbox: self._do_replace(tb.toPlainText()))
            btn_layout.addWidget(replace_btn)
            copy_btn = QPushButton("复制")
            copy_btn.setFixedSize(50, 24)
            copy_btn.setStyleSheet(self._action_btn_style("#45475a"))
            copy_btn.clicked.connect(lambda checked=False, tb=textbox: self._on_copy_text(tb))
            btn_layout.addWidget(copy_btn)
            btn_layout.addStretch()
            frame_layout.addWidget(btn_row)

            layout.addWidget(frame)
            self._rewrite_texts.append(textbox)
            self._rewrite_replace_btns.append(replace_btn)
            self._rewrite_copy_btns.append(copy_btn)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #45475a;")
        layout.addWidget(sep2)

        layout.addWidget(QLabel("自定义指令："))
        self._custom_entry = QTextEdit()
        self._custom_entry.setFixedHeight(40)
        self._custom_entry.setStyleSheet("QTextEdit { background: #181825; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; font-size: 12px; padding: 4px; }")
        layout.addWidget(self._custom_entry)

        self._custom_btn = QPushButton("生成")
        self._custom_btn.setFixedSize(60, 26)
        self._custom_btn.setStyleSheet(self._action_btn_style("#45475a"))
        self._custom_btn.clicked.connect(self._on_custom_generate)
        layout.addWidget(self._custom_btn)
        layout.addStretch()

        scroll.setWidget(container)
        self._tabs.addTab(scroll, "优化")

    def _build_translate_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        lang_widget = QWidget()
        lang_layout = QHBoxLayout(lang_widget)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        lang_layout.addWidget(QLabel("源语言："))
        self._source_lang = QComboBox()
        self._source_lang.addItems(["auto", "zh-CN", "en", "ja", "ko", "fr", "de", "es", "ru", "pt"])
        self._source_lang.setCurrentText(config.get("translation", "source_lang", default="auto"))
        self._source_lang.setFixedWidth(90)
        self._source_lang.setStyleSheet(self._combo_style())
        lang_layout.addWidget(self._source_lang)
        lang_layout.addWidget(QLabel("目标语言："))
        self._target_lang = QComboBox()
        self._target_lang.addItems(["zh-CN", "en", "ja", "ko", "fr", "de", "es", "ru", "pt"])
        self._target_lang.setCurrentText(config.get("translation", "target_lang", default="zh-CN"))
        self._target_lang.setFixedWidth(90)
        self._target_lang.setStyleSheet(self._combo_style())
        lang_layout.addWidget(self._target_lang)
        lang_layout.addStretch()
        layout.addWidget(lang_widget)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #45475a;")
        layout.addWidget(sep)

        layout.addWidget(QLabel("主翻译结果："))
        self._translation_text = QTextEdit()
        self._translation_text.setReadOnly(True)
        self._translation_text.setFixedHeight(60)
        self._translation_text.setStyleSheet("QTextEdit { background: #181825; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; font-size: 12px; padding: 4px; }")
        layout.addWidget(self._translation_text)

        trans_btn_row = QWidget()
        trans_btn_layout = QHBoxLayout(trans_btn_row)
        trans_btn_layout.setContentsMargins(0, 0, 0, 0)
        self._trans_replace_btn = QPushButton("替换原文")
        self._trans_replace_btn.setFixedSize(65, 24)
        self._trans_replace_btn.setStyleSheet(self._action_btn_style("#6c5ce7"))
        self._trans_replace_btn.clicked.connect(lambda checked=False: self._do_replace(self._translation_text.toPlainText()))
        trans_btn_layout.addWidget(self._trans_replace_btn)
        self._trans_copy_btn = QPushButton("复制")
        self._trans_copy_btn.setFixedSize(50, 24)
        self._trans_copy_btn.setStyleSheet(self._action_btn_style("#45475a"))
        self._trans_copy_btn.clicked.connect(lambda checked=False: self._on_copy_text(self._translation_text))
        trans_btn_layout.addWidget(self._trans_copy_btn)
        trans_btn_layout.addStretch()
        layout.addWidget(trans_btn_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #45475a;")
        layout.addWidget(sep2)

        layout.addWidget(QLabel("备选翻译："))
        self._alt_text = QTextEdit()
        self._alt_text.setReadOnly(True)
        self._alt_text.setFixedHeight(60)
        self._alt_text.setStyleSheet("QTextEdit { background: #181825; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; font-size: 12px; padding: 4px; }")
        layout.addWidget(self._alt_text)

        alt_btn_row = QWidget()
        alt_btn_layout = QHBoxLayout(alt_btn_row)
        alt_btn_layout.setContentsMargins(0, 0, 0, 0)
        self._alt_replace_btn = QPushButton("替换原文")
        self._alt_replace_btn.setFixedSize(65, 24)
        self._alt_replace_btn.setStyleSheet(self._action_btn_style("#6c5ce7"))
        self._alt_replace_btn.clicked.connect(lambda checked=False: self._do_replace(self._alt_text.toPlainText()))
        alt_btn_layout.addWidget(self._alt_replace_btn)
        self._alt_copy_btn = QPushButton("复制")
        self._alt_copy_btn.setFixedSize(50, 24)
        self._alt_copy_btn.setStyleSheet(self._action_btn_style("#45475a"))
        self._alt_copy_btn.clicked.connect(lambda checked=False: self._on_copy_text(self._alt_text))
        alt_btn_layout.addWidget(self._alt_copy_btn)
        alt_btn_layout.addStretch()
        layout.addWidget(alt_btn_row)
        layout.addStretch()

        scroll.setWidget(container)
        self._tabs.addTab(scroll, "翻译")

    def _build_bottom_bar(self, layout: QVBoxLayout):
        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setStyleSheet(f"""
            background: #181825; border-bottom-left-radius: {self._radius}px;
            border-bottom-right-radius: {self._radius}px;
        """)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(8, 0, 8, 0)

        settings_btn = QPushButton("\u2699 设置")
        settings_btn.setFixedHeight(26)
        settings_btn.setStyleSheet(self._btn_style())
        settings_btn.clicked.connect(self._on_settings)
        bar_layout.addWidget(settings_btn)

        self._regenerate_btn = QPushButton("\U0001f504 重新生成")
        self._regenerate_btn.setFixedHeight(26)
        self._regenerate_btn.setStyleSheet(self._btn_style())
        self._regenerate_btn.clicked.connect(self._on_regenerate)
        bar_layout.addWidget(self._regenerate_btn)

        self._top_toggle_btn = QPushButton("\U0001f4cc 置顶")
        self._top_toggle_btn.setFixedHeight(26)
        self._top_toggle_btn.setStyleSheet(self._btn_style())
        self._top_toggle_btn.clicked.connect(self._toggle_pin)
        bar_layout.addWidget(self._top_toggle_btn)

        bar_layout.addStretch()
        self._model_combo = QComboBox()
        self._model_combo.setFixedWidth(140)
        self._model_combo.setStyleSheet(self._combo_style())
        self._model_combo.currentIndexChanged.connect(self._on_model_combo_changed)
        bar_layout.addWidget(self._model_combo)
        self._refresh_model_combo()

        layout.addWidget(bar)

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

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._resizing = False
        self._resize_edge = ""
        self._save_geometry()

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
            self._grammar_header.setText("语法检查 ▶")
        else:
            self._grammar_container.show()
            self._grammar_header.setText("语法检查 ▼")

    def _populate_grammar_issues(self, issues: list):
        while self._grammar_layout.count():
            item = self._grammar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        self._grammar_header.show()
        self._grammar_container.show()
        self._grammar_header.setText("语法检查 ▼")

        if not issues:
            no_issues = QLabel("未发现问题 ✓")
            no_issues.setStyleSheet("color: #a6e3a1; font-size: 12px; font-weight: 500;")
            self._grammar_layout.addWidget(no_issues)
            return

        for issue in issues:
            original = html.escape(issue.get("original", ""))
            suggestion = html.escape(issue.get("suggestion", ""))
            reason = issue.get("reason", "")
            severity = issue.get("severity", "warning")

            card = QFrame()
            card.setStyleSheet(
                "QFrame { background: #313244; border: 1px solid #45475a; border-radius: 8px; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 6, 8, 6)
            card_layout.setSpacing(3)

            badge_text = "错误" if severity == "error" else "警告"
            badge_color = "#f38ba8" if severity == "error" else "#fab387"
            badge = QLabel(badge_text)
            badge.setFixedSize(32, 18)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                f"QLabel {{ background: {badge_color}; color: #1e1e2e; "
                f"border-radius: 4px; font-size: 10px; font-weight: 700; }}"
            )

            orig_label = QLabel(f"<s style='color:#f38ba8;'>{original}</s>")
            orig_label.setWordWrap(True)
            orig_label.setStyleSheet("font-size: 12px;")
            orig_label.setTextFormat(Qt.RichText)

            header_row = QHBoxLayout()
            header_row.addWidget(badge)
            header_row.addWidget(orig_label, 1)
            card_layout.addLayout(header_row)

            sugg_label = QLabel(f"→ {suggestion}")
            sugg_label.setWordWrap(True)
            sugg_label.setStyleSheet("color: #a6e3a1; font-size: 12px;")
            card_layout.addWidget(sugg_label)

            reason_label = QLabel(reason)
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet("color: #6c7086; font-size: 11px;")
            card_layout.addWidget(reason_label)

            self._grammar_layout.addWidget(card)

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
        self._model_combo.addItem("Fast", "fast")
        self._model_combo.addItem("Quality", "quality")
        custom_models = config.get("models", "custom_models", default=[])
        for i, cm in enumerate(custom_models):
            label = f"{cm.get('provider','')}-{cm.get('model_name','')}"
            self._model_combo.addItem(label, f"custom:{i}")

        config_key = "optimize_model" if self._current_mode == "optimize" else "translate_model"
        default_val = "fast" if self._current_mode == "optimize" else "quality"
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
            btn.setStyleSheet(self._style_btn_style(sid == style_id))
        if self._current_text:
            self._do_optimize()

    # ---- LLM calls ----

    def _do_optimize(self):
        if self._is_loading:
            return
        self._is_loading = True
        self._set_loading_state(True)
        style_label = FloatingWindow._get_style_label(self._current_style)

        def on_done(result, error):
            run_on_main(lambda: self._on_optimize_done(result, error))

        optimize_text(
            self._current_text,
            style=self._current_style,
            style_label=style_label,
            model_type=config.get("general", "optimize_model", default="fast"),
            on_done=on_done,
        )

    def _on_optimize_done(self, result, error):
        self._is_loading = False
        self._set_loading_state(False)
        if error:
            self._show_error(error)
            return
        if isinstance(result, dict):
            issues = result.get("grammar_issues", [])
            self._populate_grammar_issues(issues)

        if result and "rewrites" in result:
            rewrites = result["rewrites"]
            for i, textbox in enumerate(self._rewrite_texts):
                textbox.clear()
                if i < len(rewrites):
                    rw = rewrites[i]
                    content = rw.get("text", "")
                    textbox.setPlainText(content)
                else:
                    textbox.setPlainText("暂无更多版本")
        else:
            self._show_raw_text(result)

    def _do_translate(self):
        if self._is_loading:
            return
        self._is_loading = True
        self._set_loading_state(True)

        def on_done(result, error):
            run_on_main(lambda: self._on_translate_done(result, error))

        translate_text(
            self._current_text,
            source_lang=self._source_lang.currentText(),
            target_lang=self._target_lang.currentText(),
            model_type=config.get("general", "translate_model", default="quality"),
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
            alternative = result.get("alternative", "")
            self._translation_text.setPlainText(translation or "无结果")
            self._alt_text.setPlainText(alternative if alternative else "无备选翻译")

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
            model_type=config.get("general", "optimize_model", default="fast"),
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
            self._rewrite_texts[0].setPlainText(text)

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
        if self._grabber.replace_text(text):
            self._show_toast("已替换")
            if config.get("general", "replace_auto_close", default=False):
                self._close()
        else:
            self._show_toast("替换失败，请手动粘贴")

    def _on_copy_text(self, textbox):
        QApplication.clipboard().setText(textbox.toPlainText())
        self._show_toast("已复制")

    def _show_toast(self, message: str):
        toast = QLabel(message, self)
        toast.setStyleSheet("QLabel { background: #45475a; color: #cdd6f4; border-radius: 8px; padding: 4px 12px; }")
        toast.adjustSize()
        toast.move((self.width() - toast.width()) // 2, self.height() - 40)
        toast.show()
        QTimer.singleShot(1500, toast.deleteLater)

    def _show_error(self, message: str):
        for textbox in self._rewrite_texts:
            textbox.setPlainText(message)

    def _show_raw_text(self, result):
        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2)
        self._rewrite_texts[0].setPlainText(content)

    def _set_loading_state(self, loading: bool):
        self._regenerate_btn.setText("\u23f3 加载中..." if loading else "\U0001f504 重新生成")

    def _toggle_pin(self):
        self._pinned = not self._pinned
        flags = self.windowFlags()
        if self._pinned:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self._pin_btn.setText("\U0001f4cc" if self._pinned else "\U0001f4cd")
        self._top_toggle_btn.setText("\U0001f4cc 置顶" if self._pinned else "\U0001f4cd 取消置顶")
        self.show()

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
    def _btn_style(hover_color: str = "#45475a") -> str:
        return f"""
            QPushButton {{ background: transparent; color: #a6adc8; border: none;
                          font-size: 14px; padding: 2px 6px; border-radius: 4px; }}
            QPushButton:hover {{ background: {hover_color}; color: #cdd6f4; }}
        """

    @staticmethod
    def _action_btn_style(bg: str) -> str:
        return f"""
            QPushButton {{ background: {bg}; color: #cdd6f4; border: none;
                          border-radius: 6px; font-size: 11px; font-weight: 500;
                          padding: 4px 10px; }}
            QPushButton:hover {{ background: #7c6cf7; }}
        """

    @staticmethod
    def _style_btn_style(active: bool) -> str:
        bg = "#6c5ce7" if active else "#313244"
        color = "#ffffff" if active else "#a6adc8"
        return f"""
            QPushButton {{ background: {bg}; color: {color}; border: none;
                          border-radius: 6px; font-size: 12px; font-weight: 500;
                          padding: 4px 10px; }}
            QPushButton:hover {{ background: #7c6cf7; color: #fff; }}
        """

    @staticmethod
    def _combo_style() -> str:
        return """
            QComboBox { background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                        border-radius: 6px; padding: 4px 10px; font-size: 12px; }
            QComboBox:hover { border-color: #6c5ce7; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #313244; color: #cdd6f4;
                                          selection-background-color: #6c5ce7;
                                          border: 1px solid #45475a; border-radius: 4px; }
        """

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
