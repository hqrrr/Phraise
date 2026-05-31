from .config import config

import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea,
    QWidget, QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton,
    QFrame, QApplication, QListWidget, QMessageBox,
)


class SettingsPanel(QDialog):
    """Settings panel for configuring models, styles, triggers, and appearance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 - PhrAIse")
        self.resize(550, 500)
        self.setMinimumSize(500, 400)
        self.setStyleSheet("QDialog { background: #1e1e2e; }")
        flags = self.windowFlags()
        flags &= ~Qt.WindowContextHelpButtonHint
        flags |= Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)

        self._custom_model_entries: list[dict] = []
        self._custom_model_list_layout = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #1e1e2e; }
            QTabBar::tab { background: #313244; color: #a6adc8; padding: 8px 20px;
                           border: none; font-size: 13px; font-weight: 500; }
            QTabBar::tab:selected { background: #6c5ce7; color: #fff; }
            QTabBar::tab:hover:!selected { background: #45475a; }
        """)
        tabs.addTab(self._build_model_tab(), "模型")
        tabs.addTab(self._build_style_tab(), "样式")
        tabs.addTab(self._build_trigger_tab(), "触发")
        tabs.addTab(self._build_appearance_tab(), "外观")
        layout.addWidget(tabs)

        save_btn = QPushButton("保存并关闭")
        save_btn.setFixedHeight(36)
        save_btn.setStyleSheet("""
            QPushButton { background: #6c5ce7; color: white; border: none;
                          border-radius: 8px; font-size: 13px; font-weight: 600;
                          padding: 6px 24px; }
            QPushButton:hover { background: #7c6cf7; }
        """)
        save_btn.clicked.connect(self._on_save)
        layout.addWidget(save_btn, alignment=Qt.AlignCenter)

    def _build_model_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(6)

        fast_cfg = config.get("models", "fast", default={})
        quality_cfg = config.get("models", "quality", default={})

        layout.addWidget(QLabel("功能模型分配"))
        self._build_assign_row(layout, "优化模型：", "optimize_model")
        self._build_assign_row(layout, "翻译模型：", "translate_model")

        layout.addSpacing(12)

        self._model_entries = {}
        self._build_model_section(layout, "快速模型", "fast", fast_cfg)
        self._build_model_section(layout, "高质量模型", "quality", quality_cfg)
        layout.addSpacing(12)
        self._build_custom_model_section(layout)
        layout.addStretch()

        scroll.setWidget(w)
        return scroll

    def _build_assign_row(self, layout, label_text, config_key):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(80)
        lbl.setStyleSheet("color: #a6adc8; font-size: 12px;")
        rl.addWidget(lbl)
        combo = QComboBox()
        combo.addItem("快速 (fast)", "fast")
        combo.addItem("高质量 (quality)", "quality")
        customs = config.get("models", "custom_models", default=[])
        for i, cm in enumerate(customs):
            label = f"{cm.get('provider','')}-{cm.get('model_name','')}"
            combo.addItem(label, f"custom:{i}")
        current = config.get("general", config_key, default="fast")
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.setStyleSheet(self._combo_style())
        combo.setFixedWidth(220)
        rl.addWidget(combo)
        rl.addStretch()
        layout.addWidget(row)
        setattr(self, f"_assign_{config_key}", combo)

    def _build_model_section(self, layout, title, model_key, cfg):
        layout.addWidget(QLabel(title))
        entries = {}
        entries["provider"] = self._add_entry(layout, "Provider:", cfg.get("provider", ""))
        entries["api_base"] = self._add_entry(layout, "API Base:", cfg.get("api_base", ""))
        entries["api_key"] = self._add_entry(layout, "API Key:", cfg.get("api_key", ""), True)
        entries["model_name"] = self._add_entry(layout, "Model Name:", cfg.get("model_name", ""))
        entries["temperature"] = self._add_entry(layout, "Temperature:", str(cfg.get("temperature", 0.3)))
        entries["max_tokens"] = self._add_entry(layout, "Max Tokens:", str(cfg.get("max_tokens", 1024)))

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 2, 0, 0)

        test_btn = QPushButton("测试连接")
        test_btn.setFixedHeight(28)
        test_btn.setStyleSheet(self._small_btn_style())
        test_btn.clicked.connect(lambda checked, k=model_key: self._test_model(k))
        bl.addWidget(test_btn)

        fetch_btn = QPushButton("获取模型列表")
        fetch_btn.setFixedHeight(28)
        fetch_btn.setStyleSheet(self._small_btn_style())
        fetch_btn.clicked.connect(lambda checked, k=model_key: self._fetch_models(k))
        bl.addWidget(fetch_btn)

        status = QLabel("")
        status.setStyleSheet("color: #a6adc8; font-size: 11px; padding: 2px 8px;")
        status.setWordWrap(True)
        bl.addWidget(status, 1)
        layout.addWidget(btn_row)
        entries["status"] = status
        self._model_entries[model_key] = entries

    def _build_custom_model_section(self, layout):
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(QLabel("自定义模型"))
        add_btn = QPushButton("添加模型")
        add_btn.setFixedHeight(28)
        add_btn.setStyleSheet(self._small_btn_style())
        add_btn.clicked.connect(lambda: self._show_custom_model_dialog())
        hl.addWidget(add_btn)
        hl.addStretch()
        layout.addWidget(header)

        self._custom_model_list_layout = QVBoxLayout()
        self._custom_model_list_layout.setSpacing(4)
        layout.addLayout(self._custom_model_list_layout)

        customs = config.get("models", "custom_models", default=[])
        for cm in customs:
            entry = {
                "provider": QLineEdit(cm.get("provider", "")),
                "api_base": QLineEdit(cm.get("api_base", "")),
                "api_key": QLineEdit(cm.get("api_key", "")),
                "model_name": QLineEdit(cm.get("model_name", "")),
                "temperature": QLineEdit(str(cm.get("temperature", "0.3"))),
                "max_tokens": QLineEdit(str(cm.get("max_tokens", "1024"))),
            }
            self._custom_model_entries.append(entry)
        self._rebuild_custom_model_display()

    def _rebuild_custom_model_display(self):
        while self._custom_model_list_layout.count():
            item = self._custom_model_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, entry in enumerate(self._custom_model_entries):
            self._add_custom_model_display_row(i, entry)

    def _add_custom_model_display_row(self, idx, entry):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(6, 4, 6, 4)
        row.setStyleSheet("background: #313244; border-radius: 4px;")

        provider_lbl = QLabel(entry["provider"].text() or "—")
        provider_lbl.setFixedWidth(80)
        provider_lbl.setStyleSheet("color: #cdd6f4; font-size: 12px;")
        rl.addWidget(provider_lbl)

        model_lbl = QLabel(entry["model_name"].text() or "—")
        model_lbl.setStyleSheet("color: #a6adc8; font-size: 12px;")
        rl.addWidget(model_lbl, 1)

        edit_btn = QPushButton("编辑")
        edit_btn.setFixedSize(50, 24)
        edit_btn.setStyleSheet(self._small_btn_style())
        edit_btn.clicked.connect(lambda checked, i=idx: self._show_custom_model_dialog(i))
        rl.addWidget(edit_btn)

        del_btn = QPushButton("删除")
        del_btn.setFixedSize(50, 24)
        del_btn.setStyleSheet("""
            QPushButton { background: #45475a; color: #f38ba8; border: none;
                          border-radius: 6px; font-size: 12px; padding: 4px 12px; }
            QPushButton:hover { background: #f38ba8; color: #fff; }
        """)
        del_btn.clicked.connect(lambda checked, i=idx: self._remove_custom_model(i))
        rl.addWidget(del_btn)

        self._custom_model_list_layout.addWidget(row)

    def _show_custom_model_dialog(self, edit_idx=None):
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑自定义模型" if edit_idx is not None else "添加自定义模型")
        dialog.resize(420, 340)
        dialog.setStyleSheet("QDialog { background: #1e1e2e; }")
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setSpacing(6)

        fields: dict[str, QLineEdit] = {}
        if edit_idx is not None:
            entry = self._custom_model_entries[edit_idx]
            fields["provider"] = self._dlg_field(dlg_layout, "Provider:", entry["provider"].text())
            fields["api_base"] = self._dlg_field(dlg_layout, "API Base:", entry["api_base"].text())
            fields["api_key"] = self._dlg_field(dlg_layout, "API Key:", entry["api_key"].text(), password=True)
            fields["model_name"] = self._dlg_field(dlg_layout, "Model Name:", entry["model_name"].text())
            fields["temperature"] = self._dlg_field(dlg_layout, "Temperature:", entry["temperature"].text())
            fields["max_tokens"] = self._dlg_field(dlg_layout, "Max Tokens:", entry["max_tokens"].text())
        else:
            fields["provider"] = self._dlg_field(dlg_layout, "Provider:", "")
            fields["api_base"] = self._dlg_field(dlg_layout, "API Base:", "")
            fields["api_key"] = self._dlg_field(dlg_layout, "API Key:", "", password=True)
            fields["model_name"] = self._dlg_field(dlg_layout, "Model Name:", "")
            fields["temperature"] = self._dlg_field(dlg_layout, "Temperature:", "0.3")
            fields["max_tokens"] = self._dlg_field(dlg_layout, "Max Tokens:", "1024")

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 8, 0, 0)
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(30)
        cancel_btn.setStyleSheet(self._small_btn_style())
        cancel_btn.clicked.connect(dialog.reject)
        bl.addWidget(cancel_btn)
        bl.addStretch()
        save_btn = QPushButton("保存")
        save_btn.setFixedHeight(30)
        save_btn.setStyleSheet("""
            QPushButton { background: #6c5ce7; color: white; border: none;
                          border-radius: 6px; font-size: 12px; font-weight: 600;
                          padding: 6px 20px; }
            QPushButton:hover { background: #7c6cf7; }
        """)

        def on_save():
            if edit_idx is not None:
                entry = self._custom_model_entries[edit_idx]
                for key in fields:
                    entry[key].setText(fields[key].text())
            else:
                entry = {
                    "provider": QLineEdit(fields["provider"].text()),
                    "api_base": QLineEdit(fields["api_base"].text()),
                    "api_key": QLineEdit(fields["api_key"].text()),
                    "model_name": QLineEdit(fields["model_name"].text()),
                    "temperature": QLineEdit(fields["temperature"].text() or "0.3"),
                    "max_tokens": QLineEdit(fields["max_tokens"].text() or "1024"),
                }
                self._custom_model_entries.append(entry)
            self._rebuild_custom_model_display()
            self._refresh_assign_combos()
            dialog.accept()

        save_btn.clicked.connect(on_save)
        bl.addWidget(save_btn)
        dlg_layout.addWidget(btn_row)
        dialog.exec()

    def _remove_custom_model(self, idx):
        if 0 <= idx < len(self._custom_model_entries):
            self._custom_model_entries.pop(idx)
            self._rebuild_custom_model_display()
            self._refresh_assign_combos()

    def _refresh_assign_combos(self):
        for attr in ("_assign_optimize_model", "_assign_translate_model"):
            combo = getattr(self, attr, None)
            if combo is None:
                continue
            current = combo.currentData()
            combo.clear()
            combo.addItem("快速 (fast)", "fast")
            combo.addItem("高质量 (quality)", "quality")
            for i in range(len(self._custom_model_entries)):
                entry = self._custom_model_entries[i]
                label = f"{entry['provider'].text()}-{entry['model_name'].text()}"
                combo.addItem(label, f"custom:{i}")
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(0)

    @staticmethod
    def _dlg_field(layout, label_text, default_value="", password=False):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(90)
        lbl.setStyleSheet("color: #a6adc8; font-size: 12px;")
        rl.addWidget(lbl)
        entry = QLineEdit(default_value)
        if password:
            entry.setEchoMode(QLineEdit.Password)
        entry.setStyleSheet("QLineEdit { background: #181825; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; padding: 6px 10px; font-size: 12px; } QLineEdit:focus { border-color: #6c5ce7; }")
        rl.addWidget(entry, 1)
        layout.addWidget(row)
        return entry

    def _test_model(self, model_key):
        entries = self._model_entries[model_key]
        provider = entries["provider"].text()
        api_base = entries["api_base"].text()
        api_key = entries["api_key"].text()
        model_name = entries["model_name"].text()

        entries["status"].setText("正在测试...")
        entries["status"].setStyleSheet("color: #f9e2af; font-size: 11px; padding: 2px 8px;")
        QApplication.processEvents()

        def do_test():
            from .llm_client import test_connection
            ok, msg = test_connection(provider, api_base, api_key, model_name)
            from .dispatch import run_on_main
            run_on_main(lambda: self._on_test_done(model_key, ok, msg))

        threading.Thread(target=do_test, daemon=True).start()

    def _on_test_done(self, model_key, ok, msg):
        entries = self._model_entries[model_key]
        if ok:
            entries["status"].setText(msg)
            entries["status"].setStyleSheet("color: #a6e3a1; font-size: 11px; padding: 2px 8px;")
        else:
            entries["status"].setText(msg)
            entries["status"].setStyleSheet("color: #f38ba8; font-size: 11px; padding: 2px 8px;")

    def _fetch_models(self, model_key):
        entries = self._model_entries[model_key]
        api_base = entries["api_base"].text()
        api_key = entries["api_key"].text()

        entries["status"].setText("正在获取模型列表...")
        entries["status"].setStyleSheet("color: #f9e2af; font-size: 11px; padding: 2px 8px;")
        QApplication.processEvents()

        def do_fetch():
            from .llm_client import list_models
            names, err = list_models(api_base, api_key)
            from .dispatch import run_on_main
            run_on_main(lambda: self._on_fetch_done(model_key, names, err))

        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_fetch_done(self, model_key, names, err):
        entries = self._model_entries[model_key]
        if err:
            entries["status"].setText(err)
            entries["status"].setStyleSheet("color: #f38ba8; font-size: 11px; padding: 2px 8px;")
            return

        if not names:
            entries["status"].setText("未获取到模型")
            entries["status"].setStyleSheet("color: #a6adc8; font-size: 11px; padding: 2px 8px;")
            return

        entries["model_name"].setText(names[0])
        entries["status"].setText("已填入")
        entries["status"].setStyleSheet("color: #a6e3a1; font-size: 11px; padding: 2px 8px;")

        dialog = QDialog(self)
        dialog.setWindowTitle("选择模型")
        dialog.resize(400, 300)
        dialog.setStyleSheet("QDialog { background: #1e1e2e; }")
        dlg_layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        list_widget.addItems(names)
        list_widget.setStyleSheet("""
            QListWidget { background: #181825; color: #cdd6f4; border: 1px solid #45475a;
                          border-radius: 6px; font-size: 12px; }
            QListWidget::item:selected { background: #6c5ce7; }
        """)
        dlg_layout.addWidget(list_widget)
        select_btn = QPushButton("选择")
        select_btn.setStyleSheet(self._small_btn_style())
        select_btn.clicked.connect(lambda: (
            entries["model_name"].setText(list_widget.currentItem().text()),
            dialog.accept(),
        ))
        dlg_layout.addWidget(select_btn)
        dialog.exec()

    def _build_style_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(2)
        self._style_layout = layout

        layout.addWidget(QLabel("预设风格"))
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(6, 2, 6, 2)
        hl_id = QLabel("ID")
        hl_id.setFixedWidth(80)
        hl_id.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11px;")
        header_layout.addWidget(hl_id)
        hl_label = QLabel("名称")
        hl_label.setFixedWidth(80)
        hl_label.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11px;")
        header_layout.addWidget(hl_label)
        hl_kw = QLabel("提示关键词")
        hl_kw.setFixedWidth(100)
        hl_kw.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 11px;")
        header_layout.addWidget(hl_kw)
        header_layout.addStretch()
        layout.addWidget(header)

        self._style_entries: list[dict] = []
        styles = config.get("styles", default=[])
        for s in styles:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row.setStyleSheet("background: #313244; border-radius: 4px;")

            id_entry = QLineEdit(s.get("id", ""))
            id_entry.setFixedWidth(80)
            id_entry.setStyleSheet(self._entry_style())
            row_layout.addWidget(id_entry)

            label_entry = QLineEdit(s.get("label", ""))
            label_entry.setFixedWidth(80)
            label_entry.setStyleSheet(self._entry_style())
            row_layout.addWidget(label_entry)

            kw_entry = QLineEdit(s.get("prompt_keyword", ""))
            kw_entry.setFixedWidth(100)
            kw_entry.setStyleSheet(self._entry_style())
            row_layout.addWidget(kw_entry)

            del_btn = QPushButton("−")
            del_btn.setFixedSize(24, 24)
            del_btn.setStyleSheet("""
                QPushButton { background: #f38ba8; color: #fff; border: none;
                              border-radius: 4px; font-size: 14px; font-weight: bold; }
                QPushButton:hover { background: #f06292; }
                QPushButton:disabled { background: #45475a; color: #585b70; }
            """)
            row_layout.addWidget(del_btn)
            row_layout.addStretch()

            layout.addWidget(row)
            entry = {"id": id_entry, "label": label_entry, "keyword": kw_entry, "row": row, "delete_btn": del_btn}
            self._style_entries.append(entry)
            del_btn.clicked.connect(lambda checked, e=entry: self._remove_style_entry(e))

        # "+" add button
        add_btn = QPushButton("+ 添加风格")
        add_btn.setFixedHeight(30)
        add_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #6c5ce7; border: 1px dashed #6c5ce7;
                          border-radius: 6px; font-size: 12px; font-weight: 500; }
            QPushButton:hover { background: rgba(108, 92, 231, 0.1); }
        """)
        add_btn.clicked.connect(lambda: self._add_style_row())
        layout.addWidget(add_btn)
        self._style_add_btn = add_btn

        self._update_style_delete_buttons()
        layout.addStretch()

        scroll.setWidget(w)
        return scroll

    def _add_style_row(self, id_val="", label_val="", keyword_val=""):
        layout = self._style_layout
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 2, 6, 2)
        row.setStyleSheet("background: #313244; border-radius: 4px;")

        id_entry = QLineEdit(id_val)
        id_entry.setFixedWidth(80)
        id_entry.setStyleSheet(self._entry_style())
        row_layout.addWidget(id_entry)

        label_entry = QLineEdit(label_val)
        label_entry.setFixedWidth(80)
        label_entry.setStyleSheet(self._entry_style())
        row_layout.addWidget(label_entry)

        kw_entry = QLineEdit(keyword_val)
        kw_entry.setFixedWidth(100)
        kw_entry.setStyleSheet(self._entry_style())
        row_layout.addWidget(kw_entry)

        del_btn = QPushButton("−")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet("""
            QPushButton { background: #f38ba8; color: #fff; border: none;
                          border-radius: 4px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background: #f06292; }
            QPushButton:disabled { background: #45475a; color: #585b70; }
        """)
        row_layout.addWidget(del_btn)
        row_layout.addStretch()

        entry = {"id": id_entry, "label": label_entry, "keyword": kw_entry, "row": row, "delete_btn": del_btn}
        self._style_entries.append(entry)
        del_btn.clicked.connect(lambda checked, e=entry: self._remove_style_entry(e))

        add_idx = layout.indexOf(self._style_add_btn)
        layout.insertWidget(add_idx, row)
        self._update_style_delete_buttons()

    def _remove_style_entry(self, entry):
        self._style_layout.removeWidget(entry["row"])
        entry["row"].setParent(None)
        entry["row"].deleteLater()
        self._style_entries.remove(entry)
        self._update_style_delete_buttons()

    def _update_style_delete_buttons(self):
        enabled = len(self._style_entries) > 1
        for entry in self._style_entries:
            entry["delete_btn"].setEnabled(enabled)

    def _build_trigger_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(4)

        trigger_cfg = config.get("trigger", default={})
        layout.addWidget(QLabel("快捷键设置"))

        self._hk_trigger, self._hk_trigger_status = self._build_hotkey_row(
            layout, "触发快捷键:", trigger_cfg.get("hotkey_trigger", "ctrl+c+c"))
        self._hk_trigger.setPlaceholderText("例如: ctrl+c+c 或 ctrl+shift+o")
        # Reconnect trigger hotkey to use double-tap-aware validation
        try:
            self._hk_trigger.textChanged.disconnect()
        except RuntimeError:
            pass
        self._hk_trigger.textChanged.connect(
            lambda text, e=self._hk_trigger, s=self._hk_trigger_status:
                self._on_hotkey_text_changed_trigger(text, e, s))
        # Re-validate initial value (e.g. "ctrl+c+c" fails _validate_hotkey used by _build_hotkey_row)
        if self._validate_trigger_hotkey(self._hk_trigger.text()):
            self._hk_trigger.setStyleSheet(self._hotkey_entry_style(True))
            self._hk_trigger_status.setText("")
        self._hk_toggle, self._hk_toggle_status = self._build_hotkey_row(
            layout, "切换悬浮球:", trigger_cfg.get("hotkey_toggle_ball", "ctrl+shift+b"))

        layout.addStretch()

        scroll.setWidget(w)
        return scroll

    @staticmethod
    def _validate_hotkey(text: str) -> bool:
        if not text or not text.strip():
            return False
        parts = [p.strip().lower() for p in text.split("+")]
        if not parts:
            return False

        modifiers = {"ctrl", "control", "alt", "shift", "win", "cmd", "super"}
        single_keys = set("abcdefghijklmnopqrstuvwxyz0123456789")
        special_keys = {"space", "enter", "tab", "esc", "backspace",
                        "delete", "up", "down", "left", "right"}
        function_keys = {f"f{i}" for i in range(1, 13)}

        modifier_count = 0
        key_count = 0

        for p in parts:
            if not p:
                return False
            if p in modifiers:
                modifier_count += 1
            elif p in single_keys or p in special_keys or p in function_keys:
                key_count += 1
            else:
                return False

        return 1 <= modifier_count <= 3 and key_count == 1

    @staticmethod
    def _validate_trigger_hotkey(text: str) -> bool:
        if not text or not text.strip():
            return False
        parts = [p.strip().lower() for p in text.split("+")]
        if not parts or any(not p for p in parts):
            return False

        modifiers = {"ctrl", "control", "alt", "shift", "win", "cmd", "super"}
        single_keys = set("abcdefghijklmnopqrstuvwxyz0123456789")
        special_keys = {"space", "enter", "tab", "esc", "backspace",
                        "delete", "up", "down", "left", "right"}
        function_keys = {f"f{i}" for i in range(1, 13)}
        valid_keys = single_keys | special_keys | function_keys

        # Double-tap: last two parts are the same single character
        if len(parts) >= 2 and parts[-1] == parts[-2] and len(parts[-1]) == 1:
            mod_parts = parts[:-2]
            if not mod_parts:
                return parts[-1] in valid_keys
            return all(m in modifiers for m in mod_parts) and parts[-1] in valid_keys

        # Single combo validation
        modifier_count = 0
        key_count = 0
        for p in parts:
            if p in modifiers:
                modifier_count += 1
            elif p in valid_keys:
                key_count += 1
            else:
                return False
        return modifier_count >= 1 and key_count == 1 and modifier_count <= 3

    @staticmethod
    def _hotkey_entry_style(valid: bool = True) -> str:
        border = "#45475a" if valid else "#f38ba8"
        return (
            f"QLineEdit {{ background: #181825; color: #cdd6f4;"
            f" border: 1px solid {border}; border-radius: 6px;"
            f" padding: 6px 10px; font-size: 12px; }}"
            f" QLineEdit:focus {{ border-color: #6c5ce7; }}"
        )

    def _build_hotkey_row(self, layout, label_text, default_value):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(120)
        lbl.setStyleSheet("color: #a6adc8;")
        row_layout.addWidget(lbl)

        entry = QLineEdit(default_value)
        entry.setPlaceholderText("例如: ctrl+shift+o")
        entry.setStyleSheet(self._hotkey_entry_style(True))
        row_layout.addWidget(entry, 1)

        status = QLabel("")
        status.setFixedWidth(80)
        status.setStyleSheet("color: #f38ba8; font-size: 11px;")
        row_layout.addWidget(status)

        layout.addWidget(row)

        if not self._validate_hotkey(default_value):
            entry.setStyleSheet(self._hotkey_entry_style(False))
            status.setText("⚠ 格式无效")

        entry.textChanged.connect(
            lambda text, e=entry, s=status: self._on_hotkey_text_changed(text, e, s)
        )

        return entry, status

    def _on_hotkey_text_changed(self, text: str, entry: QLineEdit, status_label: QLabel):
        if self._validate_hotkey(text):
            entry.setStyleSheet(self._hotkey_entry_style(True))
            status_label.setText("")
        else:
            entry.setStyleSheet(self._hotkey_entry_style(False))
            status_label.setText("⚠ 格式无效")

    def _on_hotkey_text_changed_trigger(self, text, entry, status_label):
        if not text.strip():
            entry.setStyleSheet(self._hotkey_entry_style(False))
            status_label.setText("⚠ 格式无效")
        elif self._validate_trigger_hotkey(text):
            entry.setStyleSheet(self._hotkey_entry_style(True))
            status_label.setText("")
        else:
            entry.setStyleSheet(self._hotkey_entry_style(False))
            status_label.setText("⚠ 格式无效")

    def _build_appearance_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(4)

        general_cfg = config.get("general", default={})
        ball_cfg = config.get("floating_ball", default={})

        layout.addWidget(QLabel("常规设置"))
        theme_row = QWidget()
        theme_layout = QHBoxLayout(theme_row)
        theme_layout.setContentsMargins(0, 0, 0, 0)
        theme_layout.addWidget(QLabel("主题:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["dark"])
        self._theme_combo.setCurrentText(general_cfg.get("theme", "dark"))
        self._theme_combo.setStyleSheet(self._combo_style())
        self._theme_combo.setFixedWidth(100)
        theme_layout.addWidget(self._theme_combo)
        theme_layout.addStretch()
        layout.addWidget(theme_row)

        self._startup_cb = QCheckBox("开机自启")
        self._startup_cb.setChecked(general_cfg.get("start_with_windows", False))
        self._startup_cb.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(self._startup_cb)

        self._start_min_cb = QCheckBox("启动时最小化")
        self._start_min_cb.setChecked(general_cfg.get("start_minimized", False))
        self._start_min_cb.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(self._start_min_cb)

        self._auto_close_cb = QCheckBox("替换后自动关闭悬浮窗")
        self._auto_close_cb.setChecked(general_cfg.get("replace_auto_close", False))
        self._auto_close_cb.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(self._auto_close_cb)

        layout.addSpacing(12)
        layout.addWidget(QLabel("悬浮球设置"))
        self._ball_opacity = self._add_entry(layout, "透明度 (0.1-1.0):", str(ball_cfg.get("opacity", 0.50)))
        self._ball_size = self._add_entry(layout, "大小 (px):", str(ball_cfg.get("size", 52)))
        layout.addStretch()

        scroll.setWidget(w)
        return scroll

    def _add_entry(self, layout, label_text, default_value="", password=False):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(120)
        lbl.setStyleSheet("color: #a6adc8;")
        row_layout.addWidget(lbl)
        entry = QLineEdit(default_value)
        if password:
            entry.setEchoMode(QLineEdit.Password)
        entry.setStyleSheet(self._entry_style())
        row_layout.addWidget(entry, 1)
        layout.addWidget(row)
        return entry

    def _on_save(self):
        data = config.data

        for model_key in ("fast", "quality"):
            e = self._model_entries[model_key]
            data["models"][model_key] = {
                "provider": e["provider"].text(),
                "api_base": e["api_base"].text(),
                "api_key": e["api_key"].text(),
                "model_name": e["model_name"].text(),
                "temperature": float(e["temperature"].text() or "0.3"),
                "max_tokens": int(e["max_tokens"].text() or "1024"),
            }

        customs = []
        for entry in self._custom_model_entries:
            customs.append({
                "provider": entry["provider"].text(),
                "api_base": entry["api_base"].text(),
                "api_key": entry["api_key"].text(),
                "model_name": entry["model_name"].text(),
                "temperature": float(entry["temperature"].text() or "0.3"),
                "max_tokens": int(entry["max_tokens"].text() or "1024"),
            })
        data["models"]["custom_models"] = customs

        data["general"]["optimize_model"] = self._assign_optimize_model.currentData()
        data["general"]["translate_model"] = self._assign_translate_model.currentData()

        styles = []
        for entry in self._style_entries:
            styles.append({
                "id": entry["id"].text(),
                "label": entry["label"].text(),
                "prompt_keyword": entry["keyword"].text(),
            })
        if styles:
            data["styles"] = styles

        hk_invalid = (
            not self._validate_trigger_hotkey(self._hk_trigger.text()) or
            not self._validate_hotkey(self._hk_toggle.text())
        )
        if hk_invalid:
            QMessageBox.warning(self, "格式错误", "快捷键格式无效，请检查后重试。")
            return

        data["trigger"]["hotkey_trigger"] = self._hk_trigger.text()
        data["trigger"].pop("hotkey_optimize", None)
        data["trigger"].pop("hotkey_translate", None)
        data["trigger"]["hotkey_toggle_ball"] = self._hk_toggle.text()

        data["general"]["theme"] = self._theme_combo.currentText()
        data["general"]["start_with_windows"] = self._startup_cb.isChecked()
        data["general"]["start_minimized"] = self._start_min_cb.isChecked()
        data["general"]["replace_auto_close"] = self._auto_close_cb.isChecked()

        data["floating_ball"]["opacity"] = float(self._ball_opacity.text() or "0.85")
        data["floating_ball"]["size"] = int(self._ball_size.text() or "52")

        config.save()
        self.accept()

    @staticmethod
    def _small_btn_style():
        return """
            QPushButton { background: #45475a; color: #cdd6f4; border: none;
                          border-radius: 6px; font-size: 12px; padding: 4px 12px; }
            QPushButton:hover { background: #6c5ce7; color: #fff; }
        """

    @staticmethod
    def _entry_style():
        return "QLineEdit { background: #181825; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; padding: 6px 10px; font-size: 12px; } QLineEdit:focus { border-color: #6c5ce7; }"

    @staticmethod
    def _combo_style():
        return """
            QComboBox { background: #181825; color: #cdd6f4; border: 1px solid #45475a;
                        border-radius: 6px; padding: 6px 10px; font-size: 12px; }
            QComboBox:hover { border-color: #6c5ce7; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #181825; color: #cdd6f4;
                                          selection-background-color: #6c5ce7;
                                          border: 1px solid #45475a; border-radius: 4px; }
        """
