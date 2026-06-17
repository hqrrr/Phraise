# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Settings dialog UI for models, styles, triggers, and appearance.
from .config import config
from .i18n import t, SUPPORTED_LANGUAGES, set_language, get_language, add_listener, remove_listener
from .provider_manager import get_providers, init_providers
from .theme import (
    combo_style, entry_style, btn_style, tab_style, action_btn_style,
    label_style, text_edit_style, get_theme, theme_notifier,
    resolve_theme_name, rgba, list_themes, FONT_FAMILY_MONO,
    _contrast_text_color, _muted_text_color,
)

import threading

import shiboken6

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea,
    QWidget, QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton,
    QFrame, QApplication, QMessageBox, QTextEdit, QSlider,
    QCompleter,
)

import json


class NoScrollComboBox(QComboBox):
    """QComboBox that blocks scroll wheel when the dropdown popup is closed.

    Prevents accidental value changes when scrolling the settings dialog
    while the mouse cursor happens to be over a combo box.
    When the popup is open and has many items, wheel scrolls the list normally.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup_open = False

    def showPopup(self):
        self._popup_open = True
        view = self.view()
        if view is not None:
            view.setMaximumWidth(self.width())
            view.setTextElideMode(Qt.ElideRight)
            view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        completer_popup = self.completer().popup() if self.completer() else None
        if completer_popup is not None:
            completer_popup.setMaximumWidth(self.width())
            completer_popup.setTextElideMode(Qt.ElideRight)
            completer_popup.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        super().showPopup()

    def hidePopup(self):
        self._popup_open = False
        super().hidePopup()

    def wheelEvent(self, event):
        if self._popup_open:
            super().wheelEvent(event)
        else:
            event.ignore()


class SettingsPanel(QDialog):
    """Settings panel for configuring models, styles, triggers, and appearance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme_colors = get_theme(theme_notifier.current_theme)["colors"]
        self.setWindowTitle(t("settings.title"))
        self.resize(550, 500)
        self.setMinimumSize(500, 400)
        self.setStyleSheet(f"QDialog {{ background: {self._theme_colors['bg']}; }}")
        theme_notifier.theme_changed.connect(self._on_theme_changed)
        flags = self.windowFlags()
        flags &= ~Qt.WindowContextHelpButtonHint
        flags |= Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)

        self._registered_listener = False
        self._is_closing = False
        self._saved = False
        self._original_theme = resolve_theme_name(config.get("appearance", "theme", default="dark"))
        self._provider_combos: list[QComboBox] = []

        self._build_ui()

        add_listener(self._retranslate_ui)
        self._registered_listener = True
        self.finished.connect(lambda: (
            setattr(self, '_is_closing', True),
            remove_listener(self._retranslate_ui),
        ))

        init_providers(callback=self._on_providers_loaded)

    def closeEvent(self, event):
        if not self._saved and not self._is_closing:
            self._is_closing = True
            self._revert_theme()
        super().closeEvent(event)

    def reject(self):
        if not self._saved and not self._is_closing:
            self._is_closing = True
            self._revert_theme()
        super().reject()

    def _revert_theme(self):
        if theme_notifier.current_theme != self._original_theme:
            theme_notifier.set_theme(self._original_theme)

    def _on_providers_loaded(self):
        if self._is_closing:
            return
        if not shiboken6.isValid(self):
            try:
                _ = self._provider_combos
            except RuntimeError:
                return
        for combo in self._provider_combos:
            current_id = combo.currentData()
            self._populate_provider_combo(combo)
            if current_id:
                idx = combo.findData(current_id)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            else:
                idx = combo.findData("custom")
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            # Re-apply auto-fill/hide logic for the newly selected item.
            combo.blockSignals(True)
            try:
                self._apply_provider_selection(combo)
            finally:
                combo.blockSignals(False)

    @staticmethod
    def _find_provider_by_id(provider_id: str) -> dict | None:
        for p in get_providers():
            if p.get("id") == provider_id:
                return p
        return None

    @staticmethod
    def _populate_provider_combo(combo: QComboBox) -> None:
        combo.blockSignals(True)
        try:
            combo.clear()
            for provider in get_providers():
                pid = provider.get("id", "")
                label = t(f"provider.{pid}")
                if label == f"provider.{pid}":
                    label = provider.get("label", pid)
                combo.addItem(label, pid)
            combo.addItem(t("settings.provider_custom"), "custom")
        finally:
            combo.blockSignals(False)

    @staticmethod
    def _provider_for_api_base(api_base: str) -> dict | None:
        for p in get_providers():
            if p.get("api_base") == api_base:
                return p
        return None

    def _build_searchable_combo(self) -> NoScrollComboBox:
        combo = NoScrollComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(NoScrollComboBox.NoInsert)
        combo.lineEdit().setPlaceholderText(t("settings.provider_search"))

        proxy = QSortFilterProxyModel(combo)
        proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        proxy.setSourceModel(combo.model())

        completer = QCompleter(proxy, combo)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setModel(proxy)
        combo.setCompleter(completer)

        def _on_text_changed(text: str) -> None:
            proxy.setFilterFixedString(text)

        combo.lineEdit().textEdited.connect(_on_text_changed)

        def _on_completion_activated(text: str) -> None:
            idx = combo.findText(text)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        completer.activated.connect(_on_completion_activated)
        return combo

    def _apply_provider_selection(self, combo: QComboBox) -> None:
        api_base_entry = getattr(combo, "_api_base_entry", None)
        api_base_row = getattr(combo, "_api_base_row", None)
        if api_base_entry is None or api_base_row is None:
            return
        current_data = combo.currentData()
        if current_data and current_data != "custom":
            provider = self._find_provider_by_id(current_data)
            if provider:
                api_base_entry.setText(provider.get("api_base", ""))
            api_base_row.setVisible(False)
        else:
            api_base_row.setVisible(True)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(tab_style(self._theme_colors))
        self._tabs.addTab(self._build_model_tab(), t("settings.tab.models"))
        self._tabs.addTab(self._build_style_tab(), t("settings.tab.styles"))
        self._tabs.addTab(self._build_trigger_tab(), t("settings.tab.triggers"))
        self._tabs.addTab(self._build_appearance_tab(), t("settings.tab.appearance"))
        self._tabs.addTab(self._build_language_tab(), t("settings.tab.language"))
        layout.addWidget(self._tabs)

        self._save_btn = QPushButton(t("settings.btn.save"))
        self._save_btn.setFixedHeight(36)
        self._save_btn.setStyleSheet(action_btn_style(self._theme_colors, "accent"))
        self._save_btn.clicked.connect(self._on_save)
        layout.addWidget(self._save_btn, alignment=Qt.AlignCenter)

    def _build_model_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(6)

        fast_cfg = config.get("models", "model_1", default={})
        quality_cfg = config.get("models", "model_2", default={})

        layout.addWidget(QLabel(t("settings.section.model_assignment")))
        self._build_assign_row(layout, t("settings.label.optimize_model"), "optimize_model", include_harper=True)
        self._build_assign_row(layout, t("settings.label.translate_model"), "translate_model")

        # ── Harper dialect config ──
        layout.addSpacing(12)
        harper_section_label = QLabel(t("settings.section.harper"))
        harper_section_label.setStyleSheet(label_style(self._theme_colors, "text", "font-size: 14px; font-weight: 600;"))
        layout.addWidget(harper_section_label)

        dialect_row = QWidget()
        drl = QHBoxLayout(dialect_row)
        drl.setContentsMargins(0, 0, 0, 0)
        self._lbl_harper_dialect = QLabel(t("settings.label.harper_dialect"))
        self._lbl_harper_dialect.setFixedWidth(120)
        self._lbl_harper_dialect.setStyleSheet(label_style(self._theme_colors, "text_muted"))
        drl.addWidget(self._lbl_harper_dialect)

        self._harper_dialect = NoScrollComboBox()
        dialects = [
            (t("settings.dialect.american"), "American"),
            (t("settings.dialect.british"), "British"),
            (t("settings.dialect.australian"), "Australian"),
            (t("settings.dialect.canadian"), "Canadian"),
            (t("settings.dialect.indian"), "Indian"),
        ]
        for display, data in dialects:
            self._harper_dialect.addItem(display, data)
        current_dialect = config.get("harper", "dialect", default="American")
        idx = self._harper_dialect.findData(current_dialect)
        if idx >= 0:
            self._harper_dialect.setCurrentIndex(idx)
        self._harper_dialect.setStyleSheet(combo_style(self._theme_colors))
        drl.addWidget(self._harper_dialect)
        drl.addStretch()
        layout.addWidget(dialect_row)

        layout.addSpacing(12)
        llm_section_label = QLabel(t("settings.section.llm"))
        llm_section_label.setStyleSheet(label_style(self._theme_colors, "text", "font-size: 14px; font-weight: 600;"))
        layout.addWidget(llm_section_label)

        self._model_entries = {}
        self._build_model_section(layout, t("settings.model.one"), "model_1", fast_cfg)
        self._build_model_section(layout, t("settings.model.two"), "model_2", quality_cfg)
        layout.addSpacing(12)
        layout.addStretch()

        scroll.setWidget(w)
        return scroll

    def _build_assign_row(self, layout, label_text, config_key, include_harper=False):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(120)
        lbl.setStyleSheet(label_style(self._theme_colors, "text_muted", "font-size: 12px;"))
        rl.addWidget(lbl)
        combo = NoScrollComboBox()
        combo.addItem(t("settings.model.not_selected"), "")
        combo.addItem(t("settings.model.one"), "model_1")
        combo.addItem(t("settings.model.two"), "model_2")
        if include_harper:
            combo.addItem(t("settings.model.harper"), "harper")
        current = config.get("general", config_key, default="")
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(0)
        combo.setStyleSheet(combo_style(self._theme_colors))
        combo.setFixedWidth(220)
        rl.addWidget(combo)
        rl.addStretch()
        layout.addWidget(row)
        setattr(self, f"_assign_{config_key}", combo)

    def _build_provider_row(self, layout, cfg, model_key):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self._lbl_provider = QLabel(t("settings.label.provider"))
        self._lbl_provider.setFixedWidth(120)
        self._lbl_provider.setStyleSheet(label_style(self._theme_colors, "text_muted"))
        rl.addWidget(self._lbl_provider)

        combo = self._build_searchable_combo()
        self._populate_provider_combo(combo)
        combo.setStyleSheet(combo_style(self._theme_colors))
        combo.setMinimumWidth(200)
        rl.addWidget(combo, 1)
        layout.addWidget(row)

        api_base_row = QWidget()
        abl = QHBoxLayout(api_base_row)
        abl.setContentsMargins(0, 0, 0, 0)
        self._lbl_api_base = QLabel(t("settings.label.api_base"))
        self._lbl_api_base.setFixedWidth(120)
        self._lbl_api_base.setStyleSheet(label_style(self._theme_colors, "text_muted"))
        abl.addWidget(self._lbl_api_base)
        api_base_entry = QLineEdit(cfg.get("api_base", ""))
        api_base_entry.setStyleSheet(entry_style(self._theme_colors))
        abl.addWidget(api_base_entry, 1)
        layout.addWidget(api_base_row)

        saved_provider = cfg.get("provider", "")
        saved_api_base = cfg.get("api_base", "")

        combo._api_base_entry = api_base_entry
        combo._api_base_row = api_base_row
        self._provider_combos.append(combo)

        detected = None
        if self._find_provider_by_id(saved_provider):
            detected = saved_provider
        else:
            detected_provider = self._provider_for_api_base(saved_api_base)
            if detected_provider:
                detected = detected_provider.get("id")

        if detected:
            idx = combo.findData(detected)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        else:
            idx = combo.findData("custom")
            if idx >= 0:
                combo.setCurrentIndex(idx)

        combo.currentIndexChanged.connect(
            lambda _idx: self._apply_provider_selection(combo)
        )
        self._apply_provider_selection(combo)

        return combo, api_base_entry

    def _build_model_section(self, layout, title, model_key, cfg):
        layout.addWidget(QLabel(title))
        entries = {}

        provider_combo, api_base_entry = self._build_provider_row(layout, cfg, model_key)
        entries["provider_combo"] = provider_combo
        entries["api_base"] = api_base_entry

        entries["api_key"], self._lbl_api_key = self._add_entry(layout, t("settings.label.api_key"), cfg.get("api_key", ""), True)

        model_name = cfg.get("model_name", "")
        model_row = QWidget()
        ml = QHBoxLayout(model_row)
        ml.setContentsMargins(0, 0, 0, 0)
        self._lbl_model_name = QLabel(t("settings.label.model_name"))
        self._lbl_model_name.setFixedWidth(120)
        self._lbl_model_name.setStyleSheet(label_style(self._theme_colors, "text_muted"))
        ml.addWidget(self._lbl_model_name)
        model_combo = NoScrollComboBox()
        model_combo.setEditable(True)
        model_combo.setInsertPolicy(NoScrollComboBox.NoInsert)
        model_combo.setPlaceholderText(t("settings.placeholder.model_name"))
        if model_name:
            model_combo.addItem(model_name)
            model_combo.setCurrentText(model_name)
        model_combo.setStyleSheet(combo_style(self._theme_colors))
        model_combo.setMinimumWidth(200)
        ml.addWidget(model_combo, 1)

        fetch_btn = QPushButton(t("settings.btn.fetch_models"))
        fetch_btn.setFixedHeight(28)
        fetch_btn.setFixedWidth(110)
        fetch_btn.setStyleSheet(btn_style(self._theme_colors))
        fetch_btn.clicked.connect(lambda checked, k=model_key: self._fetch_models(k))
        ml.addWidget(fetch_btn)

        layout.addWidget(model_row)
        entries["model_combo"] = model_combo

        temp_val = float(cfg.get("temperature", 0.3))
        temp_row = QWidget()
        tl = QHBoxLayout(temp_row)
        tl.setContentsMargins(0, 0, 0, 0)
        self._lbl_temperature = QLabel(t("settings.label.temperature"))
        self._lbl_temperature.setFixedWidth(120)
        self._lbl_temperature.setStyleSheet(label_style(self._theme_colors, "text_muted"))
        tl.addWidget(self._lbl_temperature)
        min_lbl = QLabel("\U0001f52c")
        min_lbl.setStyleSheet(label_style(self._theme_colors, "text_muted", "font-size: 14px;"))
        min_lbl.setToolTip(t("settings.tooltip.precise"))
        tl.addWidget(min_lbl)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(int(temp_val * 100))
        slider.setStyleSheet(self._slider_style())
        tl.addWidget(slider, 1)
        max_lbl = QLabel("\u2728")
        max_lbl.setStyleSheet(label_style(self._theme_colors, "text_muted", "font-size: 14px;"))
        max_lbl.setToolTip(t("settings.tooltip.creative"))
        tl.addWidget(max_lbl)
        val_lbl = QLabel(f"{temp_val:.2f}")
        val_lbl.setFixedWidth(36)
        val_lbl.setAlignment(Qt.AlignRight)
        val_lbl.setStyleSheet(label_style(self._theme_colors, "text", "font-size: 12px;"))
        tl.addWidget(val_lbl)
        slider.valueChanged.connect(lambda v: val_lbl.setText(f"{v / 100:.2f}"))
        layout.addWidget(temp_row)
        entries["temperature_slider"] = slider

        entries["max_tokens"], self._lbl_max_tokens = self._add_entry(layout, t("settings.label.max_tokens"), str(cfg.get("max_tokens", 1024)))
        entries["extra_params"], _ = self._add_entry(layout, t("settings.label.extra_params"), cfg.get("extra_params", ""))
        entries["extra_params"].setPlaceholderText(t("settings.placeholder.extra_params"))

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 2, 0, 0)

        test_btn = QPushButton(t("settings.btn.test_connection"))
        test_btn.setFixedHeight(28)
        test_btn.setStyleSheet(btn_style(self._theme_colors))
        test_btn.clicked.connect(lambda checked, k=model_key: self._test_model(k))
        bl.addWidget(test_btn)

        status = QLabel("")
        status.setStyleSheet(label_style(self._theme_colors, "text_muted", "font-size: 11px; padding: 2px 8px;"))
        status.setWordWrap(True)
        bl.addWidget(status, 1)
        layout.addWidget(btn_row)
        entries["status"] = status
        self._model_entries[model_key] = entries

    def _refresh_assign_combos(self):
        for attr in ("_assign_optimize_model", "_assign_translate_model"):
            combo = getattr(self, attr, None)
            if combo is None:
                continue
            current = combo.currentData()
            combo.clear()
            combo.addItem(t("settings.model.not_selected"), "")
            combo.addItem(t("settings.model.one"), "model_1")
            combo.addItem(t("settings.model.two"), "model_2")
            if attr == "_assign_optimize_model":
                combo.addItem(t("settings.model.harper"), "harper")
            idx = combo.findData(current) if current else -1
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(0)

    def _dlg_field(self, layout, label_text, default_value="", password=False):
        t = self._theme_colors
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(90)
        lbl.setStyleSheet(label_style(t, "text_muted", "font-size: 12px;"))
        rl.addWidget(lbl)
        entry = QLineEdit(default_value)
        if password:
            entry.setEchoMode(QLineEdit.Password)
        entry.setStyleSheet(entry_style(t))
        rl.addWidget(entry, 1)
        layout.addWidget(row)
        return entry

    def _test_model(self, model_key):
        entries = self._model_entries[model_key]
        provider_data = entries["provider_combo"].currentData()
        provider = provider_data if provider_data and provider_data != "custom" else entries["provider_combo"].currentText()
        api_base = entries["api_base"].text()
        api_key = entries["api_key"].text()
        model_name = entries["model_combo"].currentText()

        entries["status"].setText(t("settings.status.testing"))
        entries["status"].setStyleSheet(label_style(self._theme_colors, "yellow", "font-size: 11px; padding: 2px 8px;"))
        QApplication.processEvents()

        def do_test():
            from .llm_client import test_connection
            ok, msg = test_connection(provider, api_base, api_key, model_name)
            from .dispatch import run_on_main
            run_on_main(lambda: self._on_test_done(model_key, ok, msg))

        threading.Thread(target=do_test, daemon=True).start()

    def _on_test_done(self, model_key, ok, msg):
        if self._is_closing:
            return
        if not shiboken6.isValid(self):
            try:
                _ = self._model_entries
            except RuntimeError:
                return  # C++ object already deleted
        entries = self._model_entries[model_key]
        if ok:
            entries["status"].setText(msg)
            entries["status"].setStyleSheet(label_style(self._theme_colors, "green", "font-size: 11px; padding: 2px 8px;"))
        else:
            entries["status"].setText(msg)
            entries["status"].setStyleSheet(label_style(self._theme_colors, "red", "font-size: 11px; padding: 2px 8px;"))

    def _fetch_models(self, model_key):
        entries = self._model_entries[model_key]
        api_base = entries["api_base"].text()
        api_key = entries["api_key"].text()

        entries["status"].setText(t("settings.status.fetching"))
        entries["status"].setStyleSheet(label_style(self._theme_colors, "yellow", "font-size: 11px; padding: 2px 8px;"))
        QApplication.processEvents()

        def do_fetch():
            from .llm_client import list_models
            names, err = list_models(api_base, api_key)
            from .dispatch import run_on_main
            run_on_main(lambda: self._on_fetch_done(model_key, names, err))

        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_fetch_done(self, model_key, names, err):
        if self._is_closing:
            return
        if not shiboken6.isValid(self):
            try:
                _ = self._model_entries
            except RuntimeError:
                return  # C++ object already deleted
        entries = self._model_entries[model_key]
        if err:
            entries["status"].setText(err)
            entries["status"].setStyleSheet(label_style(self._theme_colors, "red", "font-size: 11px; padding: 2px 8px;"))
            return

        if not names:
            entries["status"].setText(t("settings.status.no_models"))
            entries["status"].setStyleSheet(label_style(self._theme_colors, "text_muted", "font-size: 11px; padding: 2px 8px;"))
            return

        entries["model_combo"].clear()
        entries["model_combo"].addItems(names)
        entries["model_combo"].setCurrentIndex(0)
        entries["status"].setText(t("settings.status.models_fetched", count=len(names)))
        entries["status"].setStyleSheet(label_style(self._theme_colors, "green", "font-size: 11px; padding: 2px 8px;"))

    def _build_style_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(2)
        self._style_layout = layout

        layout.addWidget(QLabel(t("settings.section.preset_styles")))
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(6, 2, 6, 2)
        self._lbl_style_id = QLabel(t("settings.header.style_id"))
        self._lbl_style_id.setStyleSheet(label_style(self._theme_colors, "text_muted", "font-weight: bold; font-size: 11px;"))
        header_layout.addWidget(self._lbl_style_id, 1)
        hl_label = QLabel(t("settings.header.style_label"))
        hl_label.setStyleSheet(label_style(self._theme_colors, "text_muted", "font-weight: bold; font-size: 11px;"))
        header_layout.addWidget(hl_label, 1)
        hl_kw = QLabel(t("settings.header.style_keyword"))
        hl_kw.setStyleSheet(label_style(self._theme_colors, "text_muted", "font-weight: bold; font-size: 11px;"))
        header_layout.addWidget(hl_kw, 2)
        layout.addWidget(header)

        self._style_entries: list[dict] = []
        styles = config.get("styles", default=[])
        for s in styles:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row.setStyleSheet(f"background: {self._theme_colors['surface']}; border-radius: 4px;")

            id_entry = QLineEdit(s.get("id", ""))
            id_entry.setStyleSheet(entry_style(self._theme_colors))
            row_layout.addWidget(id_entry, 1)

            label_entry = QLineEdit(s.get("label", ""))
            label_entry.setStyleSheet(entry_style(self._theme_colors))
            row_layout.addWidget(label_entry, 1)

            kw_entry = QLineEdit(s.get("prompt_keyword", ""))
            kw_entry.setStyleSheet(entry_style(self._theme_colors))
            row_layout.addWidget(kw_entry, 2)

            del_btn = QPushButton("−")
            del_btn.setFixedSize(24, 24)
            del_btn.setStyleSheet(self._del_btn_style())
            row_layout.addWidget(del_btn)
            row_layout.addStretch()

            layout.addWidget(row)
            entry = {"id": id_entry, "label": label_entry, "keyword": kw_entry, "row": row, "delete_btn": del_btn}
            self._style_entries.append(entry)
            del_btn.clicked.connect(lambda checked, e=entry: self._remove_style_entry(e))

        # "+" add button
        add_btn = QPushButton(t("settings.btn.add_style"))
        add_btn.setFixedHeight(30)
        add_btn.setStyleSheet(self._add_style_btn_style())
        add_btn.clicked.connect(lambda: self._add_style_row())
        layout.addWidget(add_btn)
        self._style_add_btn = add_btn

        restart_styles = QLabel(t("settings.restart_required"))
        restart_styles.setStyleSheet(label_style(self._theme_colors, "yellow", "font-size: 12px; padding-left: 4px;"))
        layout.addWidget(restart_styles)

        self._update_style_delete_buttons()
        layout.addStretch()

        scroll.setWidget(w)
        return scroll

    def _add_style_row(self, id_val="", label_val="", keyword_val=""):
        layout = self._style_layout
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 2, 6, 2)
        row.setStyleSheet(f"background: {self._theme_colors['surface']}; border-radius: 4px;")

        id_entry = QLineEdit(id_val)
        id_entry.setStyleSheet(entry_style(self._theme_colors))
        row_layout.addWidget(id_entry, 1)

        label_entry = QLineEdit(label_val)
        label_entry.setStyleSheet(entry_style(self._theme_colors))
        row_layout.addWidget(label_entry, 1)

        kw_entry = QLineEdit(keyword_val)
        kw_entry.setStyleSheet(entry_style(self._theme_colors))
        row_layout.addWidget(kw_entry, 2)

        del_btn = QPushButton("−")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet(self._del_btn_style())
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(4)

        trigger_cfg = config.get("trigger", default={})
        layout.addWidget(QLabel(t("settings.section.hotkeys")))

        self._hk_trigger, self._hk_trigger_status = self._build_hotkey_row(
            layout, t("settings.label.trigger_hotkey"), trigger_cfg.get("hotkey_trigger", "ctrl+c+c"))
        self._hk_trigger.setPlaceholderText(t("settings.placeholder.trigger_hotkey"))
        # Reconnect trigger hotkey to use double-tap-aware validation
        try:
            self._hk_trigger.textChanged.disconnect()
        except RuntimeError:
            pass  # Signal was not connected; safe to ignore.
        self._hk_trigger.textChanged.connect(
            lambda text, e=self._hk_trigger, s=self._hk_trigger_status:
                self._on_hotkey_text_changed_trigger(text, e, s))
        if self._validate_trigger_hotkey(self._hk_trigger.text()):
            self._hk_trigger.setStyleSheet(self._hotkey_entry_style(True))
            self._hk_trigger_status.setText("")
        self._hk_toggle, self._hk_toggle_status = self._build_hotkey_row(
            layout, t("settings.label.toggle_ball"), trigger_cfg.get("hotkey_toggle_ball", "ctrl+shift+b"))

        restart_lbl = QLabel(t("settings.restart_required"))
        restart_lbl.setStyleSheet(label_style(self._theme_colors, "yellow", "font-size: 12px; padding-left: 120px;"))
        layout.addWidget(restart_lbl)

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

    def _hotkey_entry_style(self, valid: bool = True) -> str:
        t = self._theme_colors
        border = t["border"] if valid else t["red"]
        return (
            f"QLineEdit {{ background: {t['bg_darker']}; color: {t['text']};"
            f" border: 1px solid {border}; border-radius: 6px;"
            f" padding: 6px 10px; font-size: 12px; }}"
            f" QLineEdit:focus {{ border-color: {t['accent']}; }}"
        )

    def _build_hotkey_row(self, layout, label_text, default_value):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(120)
        lbl.setStyleSheet(label_style(self._theme_colors, "text_muted"))
        row_layout.addWidget(lbl)

        entry = QLineEdit(default_value)
        entry.setPlaceholderText(t("settings.placeholder.hotkey"))
        entry.setStyleSheet(self._hotkey_entry_style(True))
        row_layout.addWidget(entry, 1)

        status = QLabel("")
        status.setFixedWidth(80)
        status.setStyleSheet(label_style(self._theme_colors, "red", "font-size: 11px;"))
        row_layout.addWidget(status)

        layout.addWidget(row)

        if not self._validate_hotkey(default_value):
            entry.setStyleSheet(self._hotkey_entry_style(False))
            status.setText(t("settings.status.invalid_format"))

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
            status_label.setText(t("settings.status.invalid_format"))

    def _on_hotkey_text_changed_trigger(self, text, entry, status_label):
        if not text.strip():
            entry.setStyleSheet(self._hotkey_entry_style(False))
            status_label.setText(t("settings.status.invalid_format"))
        elif self._validate_trigger_hotkey(text):
            entry.setStyleSheet(self._hotkey_entry_style(True))
            status_label.setText("")
        else:
            entry.setStyleSheet(self._hotkey_entry_style(False))
            status_label.setText(t("settings.status.invalid_format"))

    def _build_appearance_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(4)

        general_cfg = config.get("general", default={})
        ball_cfg = config.get("floating_ball", default={})
        appearance_cfg = config.get("appearance", default={})

        layout.addWidget(QLabel(t("settings.section.general")))
        theme_row = QWidget()
        theme_layout = QHBoxLayout(theme_row)
        theme_layout.setContentsMargins(0, 0, 0, 0)
        theme_layout.addWidget(QLabel(t("settings.label.theme")))
        self._theme_combo = NoScrollComboBox()
        current_theme = resolve_theme_name(appearance_cfg.get("theme", "dark"))
        for theme_name in list_themes():
            self._theme_combo.addItem(theme_name, theme_name)
        idx = self._theme_combo.findData(current_theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        self._theme_combo.setStyleSheet(combo_style(self._theme_colors))
        self._theme_combo.setFixedWidth(200)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_combo_changed)
        theme_layout.addWidget(self._theme_combo)
        theme_layout.addStretch()
        layout.addWidget(theme_row)

        self._start_min_cb = QCheckBox(t("settings.checkbox.start_minimized"))
        self._start_min_cb.setChecked(general_cfg.get("start_minimized", False))
        self._start_min_cb.setStyleSheet(label_style(self._theme_colors, "text"))
        layout.addWidget(self._start_min_cb)

        self._auto_close_cb = QCheckBox(t("settings.checkbox.auto_close"))
        self._auto_close_cb.setChecked(general_cfg.get("replace_auto_close", False))
        self._auto_close_cb.setStyleSheet(label_style(self._theme_colors, "text"))
        layout.addWidget(self._auto_close_cb)

        layout.addSpacing(12)
        layout.addWidget(QLabel(t("settings.section.ball")))
        self._ball_opacity, _ = self._add_entry(layout, t("settings.label.opacity"), str(ball_cfg.get("opacity", 0.50)))
        self._ball_size, _ = self._add_entry(layout, t("settings.label.ball_size"), str(ball_cfg.get("size", 30)))

        restart_appear = QLabel(t("settings.restart_required"))
        restart_appear.setStyleSheet(label_style(self._theme_colors, "yellow", "font-size: 12px; padding-left: 4px;"))
        layout.addWidget(restart_appear)

        # ── Custom CSS section ──────────────────────────────────────────
        layout.addSpacing(12)
        layout.addWidget(QLabel(t("settings.label.custom_css")))
        self._custom_css_editor = QTextEdit()
        self._custom_css_editor.setMinimumHeight(120)
        self._custom_css_editor.setMaximumHeight(200)
        from PySide6.QtGui import QFont
        self._custom_css_editor.setFont(QFont(FONT_FAMILY_MONO.replace('"', "").split(",")[0].strip(), 13))
        self._custom_css_editor.setStyleSheet(
            text_edit_style(self._theme_colors)
            + f" QTextEdit {{ font-family: {FONT_FAMILY_MONO}; font-size: 13px; }}"
        )
        self._custom_css_editor.setPlaceholderText(t("settings.placeholder.css"))
        self._custom_css_editor.setPlainText(appearance_cfg.get("custom_css", ""))
        layout.addWidget(self._custom_css_editor)

        # ── Validate + Preview buttons ──────────────────────────────────
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self._css_status_label = QLabel("")
        self._css_status_label.setStyleSheet("font-size: 11px;")
        btn_layout.addWidget(self._css_status_label)

        btn_layout.addStretch()

        validate_btn = QPushButton(t("settings.btn.validate"))
        validate_btn.setFixedSize(80, 26)
        validate_btn.setStyleSheet(btn_style(self._theme_colors))
        validate_btn.clicked.connect(self._on_validate_css)
        btn_layout.addWidget(validate_btn)

        preview_btn = QPushButton(t("settings.btn.preview"))
        preview_btn.setFixedSize(80, 26)
        preview_btn.setStyleSheet(btn_style(self._theme_colors))
        preview_btn.clicked.connect(self._on_preview_css)
        btn_layout.addWidget(preview_btn)

        layout.addWidget(btn_row)

        # ── Preview frame ──────────────────────────────────────────────
        self._preview_frame = QFrame()
        self._preview_frame.setMinimumHeight(80)
        self._preview_frame.setStyleSheet(
            f"QFrame {{ background: {self._theme_colors['bg']};"
            f" border: 1px solid {self._theme_colors['border']};"
            f" border-radius: 6px; padding: 8px; }}"
        )
        preview_frame_layout = QVBoxLayout(self._preview_frame)
        preview_label = QLabel(t("settings.preview.text"))
        preview_label.setStyleSheet(label_style(self._theme_colors, "text", "font-size: 12px;"))
        preview_frame_layout.addWidget(preview_label)
        preview_btn_sample = QPushButton(t("settings.preview.button"))
        preview_btn_sample.setFixedSize(80, 24)
        preview_btn_sample.setStyleSheet(action_btn_style(self._theme_colors, "accent"))
        self._preview_btn_sample = preview_btn_sample
        preview_frame_layout.addWidget(preview_btn_sample)
        layout.addWidget(self._preview_frame)
        self._preview_frame.hide()  # Hidden until Preview is clicked

        layout.addStretch()

        scroll.setWidget(w)
        return scroll

    def _add_entry(self, layout, label_text, default_value="", password=False):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(120)
        lbl.setStyleSheet(label_style(self._theme_colors, "text_muted"))
        row_layout.addWidget(lbl)
        entry = QLineEdit(default_value)
        if password:
            entry.setEchoMode(QLineEdit.Password)
        entry.setStyleSheet(entry_style(self._theme_colors))
        row_layout.addWidget(entry, 1)
        layout.addWidget(row)
        return entry, lbl

    def _on_save(self):
        data = config.data

        for model_key in ("model_1", "model_2"):
            e = self._model_entries[model_key]
            provider_val = e["provider_combo"].currentData()

            # Skip JSON validation for Harper-assigned model slot
            if self._assign_optimize_model.currentData() != "harper":
                extra_params_text = e["extra_params"].text().strip()
                if extra_params_text:
                    try:
                        json.loads(extra_params_text)
                    except json.JSONDecodeError:
                        QMessageBox.warning(self, t("settings.dialog.format_error"),
                            t("settings.error.invalid_json", model=model_key))
                        return
            else:
                extra_params_text = e["extra_params"].text().strip()
            try:
                max_tokens_val = int(e["max_tokens"].text() or "1024")
            except ValueError:
                QMessageBox.warning(self, t("settings.dialog.format_error"),
                    t("settings.error.invalid_number", field=t("settings.label.max_tokens")))
                return
            existing = data["models"].get(model_key, {})
            existing.update({
                "provider": provider_val if provider_val and provider_val != "custom" else e["provider_combo"].currentText(),
                "api_base": e["api_base"].text(),
                "api_key": e["api_key"].text(),
                "model_name": e["model_combo"].currentText(),
                "temperature": e["temperature_slider"].value() / 100.0,
                "max_tokens": max_tokens_val,
                "extra_params": extra_params_text,
            })
            data["models"][model_key] = existing

        optimize_model = self._assign_optimize_model.currentData()
        data["general"]["optimize_model"] = optimize_model
        if optimize_model == "harper":
            data["models"]["model_1"]["mode"] = "local"
        else:
            if data["models"]["model_1"].get("mode") == "local":
                data["models"]["model_1"]["mode"] = "remote"
        data["general"]["translate_model"] = self._assign_translate_model.currentData()

        if hasattr(self, '_harper_dialect'):
            data["harper"]["dialect"] = self._harper_dialect.currentData()

        styles = []
        for entry in self._style_entries:
            styles.append({
                "id": entry["id"].text(),
                "label": entry["label"].text(),
                "prompt_keyword": entry["keyword"].text(),
            })
        data["styles"] = styles

        hk_invalid = (
            not self._validate_trigger_hotkey(self._hk_trigger.text()) or
            not self._validate_hotkey(self._hk_toggle.text())
        )
        if hk_invalid:
            QMessageBox.warning(self, t("settings.dialog.format_error"), t("settings.error.invalid_hotkey"))
            return

        data["trigger"]["hotkey_trigger"] = self._hk_trigger.text()
        data["trigger"].pop("hotkey_optimize", None)
        data["trigger"].pop("hotkey_translate", None)
        data["trigger"]["hotkey_toggle_ball"] = self._hk_toggle.text()

        data["general"]["start_minimized"] = self._start_min_cb.isChecked()
        data["general"]["replace_auto_close"] = self._auto_close_cb.isChecked()

        if "appearance" not in data:
            data["appearance"] = {}
        data["appearance"]["theme"] = self._theme_combo.currentData()
        data["appearance"]["custom_css"] = self._custom_css_editor.toPlainText()

        self._saved = True

        try:
            opacity_val = float(self._ball_opacity.text() or "0.85")
        except ValueError:
            QMessageBox.warning(self, t("settings.dialog.format_error"),
                t("settings.error.invalid_number", field=t("settings.label.opacity")))
            return

        try:
            size_val = int(self._ball_size.text() or "52")
        except ValueError:
            QMessageBox.warning(self, t("settings.dialog.format_error"),
                t("settings.error.invalid_number", field=t("settings.label.ball_size")))
            return

        data["floating_ball"]["opacity"] = opacity_val
        data["floating_ball"]["size"] = size_val

        config.save()
        self.accept()

    def _on_theme_combo_changed(self):
        theme_name = resolve_theme_name(self._theme_combo.currentData())
        theme_notifier.set_theme(theme_name)

    def _on_theme_changed(self, name: str):
        self._theme_colors = get_theme(name)["colors"]
        t = self._theme_colors

        # Dialog background
        self.setStyleSheet(f"QDialog {{ background: {t['bg']}; }}")

        # Tab widget
        self._tabs.setStyleSheet(tab_style(t))

        # Save button
        self._save_btn.setStyleSheet(action_btn_style(t, "accent"))

        # Theme combo
        self._theme_combo.setStyleSheet(combo_style(t))

        # Harper dialect combo
        self._harper_dialect.setStyleSheet(combo_style(t))

        # Assign model combos
        for attr in ("_assign_optimize_model", "_assign_translate_model"):
            c = getattr(self, attr, None)
            if c:
                c.setStyleSheet(combo_style(t))

        # Model entries
        for entries in self._model_entries.values():
            entries["provider_combo"].setStyleSheet(combo_style(t))
            entries["model_combo"].setStyleSheet(combo_style(t))
            for ek in ("api_base", "api_key", "max_tokens", "extra_params"):
                if ek in entries:
                    entries[ek].setStyleSheet(entry_style(t))
            entries["temperature_slider"].setStyleSheet(self._slider_style())
            entries["status"].setStyleSheet(label_style(t, "text_muted", "font-size: 11px; padding: 2px 8px;"))

        # Style entries
        for entry in self._style_entries:
            entry["id"].setStyleSheet(entry_style(t))
            entry["label"].setStyleSheet(entry_style(t))
            entry["keyword"].setStyleSheet(entry_style(t))
            entry["delete_btn"].setStyleSheet(self._del_btn_style())
            entry["row"].setStyleSheet(f"background: {t['surface']}; border-radius: 4px;")
        self._style_add_btn.setStyleSheet(self._add_style_btn_style())

        # Hotkey entries
        hk_trigger_valid = self._validate_trigger_hotkey(self._hk_trigger.text()) if self._hk_trigger.text().strip() else False
        self._hk_trigger.setStyleSheet(self._hotkey_entry_style(hk_trigger_valid))
        hk_toggle_valid = self._validate_hotkey(self._hk_toggle.text()) if self._hk_toggle.text().strip() else False
        self._hk_toggle.setStyleSheet(self._hotkey_entry_style(hk_toggle_valid))
        self._hk_trigger_status.setStyleSheet(label_style(t, "red", "font-size: 11px;"))
        self._hk_toggle_status.setStyleSheet(label_style(t, "red", "font-size: 11px;"))

        # Hotkey validation re-run
        if hk_trigger_valid:
            self._hk_trigger_status.setText("")
        if hk_toggle_valid:
            self._hk_toggle_status.setText("")

        # Checkboxes
        self._start_min_cb.setStyleSheet(label_style(t, "text"))
        self._auto_close_cb.setStyleSheet(label_style(t, "text"))

        # Ball entries
        self._ball_opacity.setStyleSheet(entry_style(t))
        self._ball_size.setStyleSheet(entry_style(t))

        # Custom CSS editor
        self._custom_css_editor.setStyleSheet(
            text_edit_style(t) + f" QTextEdit {{ font-family: {FONT_FAMILY_MONO}; font-size: 13px; }}"
        )

        # Preview frame
        self._preview_frame.setStyleSheet(
            f"QFrame {{ background: {t['bg']}; border: 1px solid {t['border']};"
            f" border-radius: 6px; padding: 8px; }}"
        )

        # Preview sample button
        if hasattr(self, '_preview_btn_sample'):
            self._preview_btn_sample.setStyleSheet(action_btn_style(t, "accent"))

        # Language combo
        self._lang_combo.setStyleSheet(combo_style(t))

        self.update()

    def _on_validate_css(self):
        css = self._custom_css_editor.toPlainText()
        opens = css.count("{")
        closes = css.count("}")
        if opens == closes:
            self._css_status_label.setText(t("settings.css.ok"))
            self._css_status_label.setStyleSheet(label_style(self._theme_colors, "green", "font-size: 11px;"))
        else:
            self._css_status_label.setText(t("settings.css.bracket_mismatch"))
            self._css_status_label.setStyleSheet(label_style(self._theme_colors, "red", "font-size: 11px;"))

    def _on_preview_css(self):
        css = self._custom_css_editor.toPlainText()
        if self._preview_frame:
            self._preview_frame.setStyleSheet(css)
            self._preview_frame.show()

    # ── Theme-dependent style helpers ──────────────────────────────────────

    def _slider_style(self):
        t = self._theme_colors
        return (
            f"QSlider::groove:horizontal {{ height: 6px; background: {t['surface']};"
            f" border-radius: 3px; }}"
            f"QSlider::handle:horizontal {{ background: {t['accent']};"
            f" width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }}"
            f"QSlider::handle:horizontal:hover {{ background: {t['accent_hover']}; }}"
            f"QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 3px; }}"
        )

    def _del_btn_style(self):
        t = self._theme_colors
        return (
            f"QPushButton {{ background: {t['red']}; color: {_contrast_text_color(t, t['red'])};"
            f" border: none; border-radius: 4px; font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {t['red_hover']}; }}"
            f"QPushButton:disabled {{ background: {t['surface']}; color: {_muted_text_color(t, t['surface'])}; }}"
        )

    def _add_style_btn_style(self):
        t = self._theme_colors
        text = _contrast_text_color(t, t['bg'])
        return (
            f"QPushButton {{ background: transparent; color: {text};"
            f" border: 1px dashed {t['accent']}; border-radius: 6px;"
            f" font-size: 12px; font-weight: 500; }}"
            f"QPushButton:hover {{ background: {rgba(t['accent'], 26)}; }}"
        )

    def _retranslate_ui(self):
        """Re-apply translations after language change."""
        self.setWindowTitle(t("settings.title"))
        if hasattr(self, '_tabs'):
            self._tabs.setTabText(0, t("settings.tab.models"))
            self._tabs.setTabText(1, t("settings.tab.styles"))
            self._tabs.setTabText(2, t("settings.tab.triggers"))
            self._tabs.setTabText(3, t("settings.tab.appearance"))
            self._tabs.setTabText(4, t("settings.tab.language"))
        if hasattr(self, '_save_btn'):
            self._save_btn.setText(t("settings.btn.save"))
        if hasattr(self, '_provider_combos'):
            for combo in self._provider_combos:
                current_id = combo.currentData()
                self._populate_provider_combo(combo)
                if current_id:
                    idx = combo.findData(current_id)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
        if hasattr(self, '_lbl_provider'):
            self._lbl_provider.setText(t("settings.label.provider"))
        if hasattr(self, '_lbl_api_base'):
            self._lbl_api_base.setText(t("settings.label.api_base"))
        if hasattr(self, '_lbl_api_key'):
            self._lbl_api_key.setText(t("settings.label.api_key"))
        if hasattr(self, '_lbl_model_name'):
            self._lbl_model_name.setText(t("settings.label.model_name"))
        if hasattr(self, '_lbl_temperature'):
            self._lbl_temperature.setText(t("settings.label.temperature"))
        if hasattr(self, '_lbl_max_tokens'):
            self._lbl_max_tokens.setText(t("settings.label.max_tokens"))
        if hasattr(self, '_lbl_style_id'):
            self._lbl_style_id.setText(t("settings.header.style_id"))
        if hasattr(self, '_lbl_harper_dialect'):
            self._lbl_harper_dialect.setText(t("settings.label.harper_dialect"))
        if hasattr(self, '_harper_dialect'):
            current_dialect = self._harper_dialect.currentData()
            self._harper_dialect.blockSignals(True)
            self._harper_dialect.clear()
            dialects = [
                (t("settings.dialect.american"), "American"),
                (t("settings.dialect.british"), "British"),
                (t("settings.dialect.australian"), "Australian"),
                (t("settings.dialect.canadian"), "Canadian"),
                (t("settings.dialect.indian"), "Indian"),
            ]
            for display, data in dialects:
                self._harper_dialect.addItem(display, data)
            if current_dialect:
                idx = self._harper_dialect.findData(current_dialect)
                if idx >= 0:
                    self._harper_dialect.setCurrentIndex(idx)
            self._harper_dialect.blockSignals(False)

    def _build_language_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        desc = QLabel(t("settings.label.language_desc"))
        desc.setStyleSheet(label_style(self._theme_colors, "text_muted", "font-size: 12px;"))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        lang_row = QWidget()
        lang_rl = QHBoxLayout(lang_row)
        lang_rl.setContentsMargins(0, 0, 0, 0)
        lang_lbl = QLabel(t("settings.label.language"))
        lang_lbl.setFixedWidth(120)
        lang_lbl.setStyleSheet(label_style(self._theme_colors, "text_muted"))
        lang_rl.addWidget(lang_lbl)

        self._lang_combo = NoScrollComboBox()
        self._lang_combo.setFixedWidth(200)
        self._lang_combo.setStyleSheet(combo_style(self._theme_colors))
        for code, name in SUPPORTED_LANGUAGES.items():
            self._lang_combo.addItem(name, code)
        current_lang = get_language()
        idx = self._lang_combo.findData(current_lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_rl.addWidget(self._lang_combo)
        lang_rl.addStretch()
        layout.addWidget(lang_row)

        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    def _on_language_changed(self, idx):
        if idx < 0:
            return
        lang_code = self._lang_combo.itemData(idx)
        if lang_code:
            set_language(lang_code)
