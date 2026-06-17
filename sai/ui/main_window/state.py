from PyQt6 import QtGui

from sai.storage.cache import cache_size_bytes, clear_cache
from sai.ui.popups import ThemedMessageDialog

class StateMixin:

    def _set_status(self, key: str, **kwargs):
        self._status_key = key
        self._status_kwargs = dict(kwargs)
        if key == "error" and hasattr(self, "progress"):
            self.progress.setValue(0)
        self._render_status()

    def _render_status(self):
        if not hasattr(self, "lbl_status"):
            return
        if self._status_kwargs:
            self.lbl_status.setText(self.i18n.fmt(self._status_key, **self._status_kwargs))
        else:
            self.lbl_status.setText(self.i18n.t(self._status_key))

    def _load_session(self):
        api_key = self.settings.value("api_key", "", type=str) or ""
        profile_url = self.settings.value("profile_url", "", type=str) or ""
        lang = self.settings.value("language", "en", type=str) or "en"
        self.performance_mode = self.settings.value("performance_mode", "auto", type=str) or "auto"
        if self.performance_mode not in ("auto", "eco", "fast"):
            self.performance_mode = "auto"
        self._apply_performance_limits()
        self.icons_enabled = self.settings.value("icons_enabled", True, type=bool)

        if api_key:
            self.edt_key.setText(api_key)
        if profile_url:
            self.edt_profile.setText(profile_url)

        lang_index = self.cmb_lang.findData(lang)
        if lang_index >= 0:
            self.cmb_lang.blockSignals(True)
            self.cmb_lang.setCurrentIndex(lang_index)
            self.cmb_lang.blockSignals(False)
            self.i18n.set_lang(lang)

        perf_index = self.cmb_performance.findData(self.performance_mode)
        if perf_index >= 0:
            self.cmb_performance.blockSignals(True)
            self.cmb_performance.setCurrentIndex(perf_index)
            self.cmb_performance.blockSignals(False)

        icons_index = self.cmb_icons.findData(self.icons_enabled)
        if icons_index >= 0:
            self.cmb_icons.blockSignals(True)
            self.cmb_icons.setCurrentIndex(icons_index)
            self.cmb_icons.blockSignals(False)

    def _save_session(self):
        self.settings.setValue("api_key", self.edt_key.text().strip())
        self.settings.setValue("profile_url", self.edt_profile.text().strip())
        self.settings.setValue("language", self.cmb_lang.currentData() or "en")
        self.settings.setValue("performance_mode", self.performance_mode)
        self.settings.setValue("icons_enabled", self.icons_enabled)
        self.settings.sync()

    def closeEvent(self, event: QtGui.QCloseEvent):
        self._save_session()
        super().closeEvent(event)

    def on_ui_lang_changed(self):
        lang = self.cmb_lang.currentData() or "en"
        self.i18n.set_lang(lang)
        self.settings.setValue("language", lang)
        self.settings.sync()
        self._retranslate_ui()
        if self.table.rowCount() > 0:
            self.refresh_table(update_status=False)

    def _format_cache_size(self, size: int) -> str:
        size = max(0, int(size or 0))
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def _update_cache_button_text(self, force: bool = False) -> None:
        if not hasattr(self, "btn_clear_cache"):
            return
        size = cache_size_bytes()
        if not force and size == self._last_cache_size_bytes:
            return
        self._last_cache_size_bytes = size
        self.btn_clear_cache.setText(f"{self.i18n.t('clear_cache')} ({self._format_cache_size(size)})")

    def on_clear_cache(self):
        self._stop_icon_downloads()
        clear_cache()
        self.icon_cache.clear()
        self._last_cache_size_bytes = None
        self._update_cache_button_text(force=True)
        if self.icons_enabled:
            self.refresh_table(update_status=False)
        ThemedMessageDialog.information(self, self.i18n.t("info"), self.i18n.t("cache_cleared"))
        self._clear_input_selection_after_dialog(self.btn_clear_cache)

    def on_performance_mode_changed(self):
        mode = self.cmb_performance.currentData() or "auto"
        if mode not in ("auto", "eco", "fast"):
            mode = "auto"
        if mode == self.performance_mode:
            return
        self.performance_mode = mode
        self._apply_performance_limits()
        self.settings.setValue("performance_mode", self.performance_mode)
        self.settings.sync()
        if not self.cancel_event.is_set() and self._game_queue:
            self._start_next_jobs()
        self._kick_icon_prefetch()

    def on_icons_mode_changed(self):
        enabled = bool(self.cmb_icons.currentData())
        if enabled == self.icons_enabled:
            return

        self.icons_enabled = enabled
        self.settings.setValue("icons_enabled", self.icons_enabled)
        self.settings.sync()

        if self.icons_enabled:
            self._schedule_visible_icon_load()
        else:
            self._stop_icon_downloads()

        self.refresh_table(update_status=False)