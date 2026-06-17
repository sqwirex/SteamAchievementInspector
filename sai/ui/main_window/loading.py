from contextlib import suppress
from collections import deque
from typing import Dict, List

from PyQt6 import QtCore

from sai.storage.cache import read_user_achievements, write_user_achievements
from sai.core.models import Achievement
from sai.services.steam_api import SteamAPI
from sai.services.workers import GameFetchWorker, ListGamesWorker
from sai.ui.popups import ThemedMessageDialog
from sai.ui.widgets import CustomComboBox

UNKNOWN_ERROR_PREFIX = "__SAI_UNHANDLED_ERROR__\n"


class LoadingMixin:

    def on_fetch(self):
        url = self.edt_profile.text().strip()
        key = self.edt_key.text().strip()
        lang = self.cmb_lang.currentData() or "en"

        if not url:
            ThemedMessageDialog.warning(self, self.i18n.t("warning"), self.i18n.t("enter_profile"))
            return
        if not key:
            ThemedMessageDialog.warning(self, self.i18n.t("warning"), self.i18n.t("enter_key"))
            return
        if not SteamAPI.looks_like_valid_key_format(key):
            ThemedMessageDialog.warning(self, self.i18n.t("warning"), self.i18n.t("key_warn"))
            return

        self._save_session()

        self.cancel_event.clear()
        self._stopped_during_game_list_loading = False
        self._loading_game_list = True
        self._export_blocked_until_ready = True
        self._load_error_reported = False
        self.btn_fetch.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress.setValue(0)
        self._set_status("preparing_load")
        self.achievements.clear()
        self._achievement_keys.clear()
        self._achievement_loose_keys.clear()
        self._analysis_cache_signature = None
        self._analysis_cache_deltas.clear()
        self._analysis_cache_exact_count.clear()
        self.loaded_games = 0
        self.games_index.clear()
        self._game_queue.clear()
        self._active_workers = 0
        self._workers.clear()

        self.cmb_game.blockSignals(True)
        self.cmb_game.clear()
        self.cmb_game.addItem(self.i18n.t("all_games"), userData=None)
        self.cmb_game.setEnabled(False)
        self.cmb_game.blockSignals(False)
        self.table_model.clear()
        self._stop_icon_downloads()

        self.current_api_key = key
        self.current_profile_url = url

        lgw = ListGamesWorker(key, url, lang)
        self._workers.append(lgw)
        lgw.signals.loading_games.connect(self._on_game_list_loading_started)
        lgw.signals.finished.connect(
            lambda steamid64, games, w=lgw: (self._safe_remove_worker(w),
                                             self._on_games_list_ready(key, steamid64, games))
        )
        lgw.signals.error.connect(
            lambda msg, w=lgw: (self._safe_remove_worker(w), self._on_game_list_error(msg))
        )
        self.threadpool.start(lgw)

    def _hide_open_popups(self):
        for combo in self.findChildren(CustomComboBox):
            combo.hidePopup()

    def _safe_remove_worker(self, w: QtCore.QRunnable):
        with suppress(ValueError):
            self._workers.remove(w)

    def on_stop(self):
        if not self._export_blocked_until_ready:
            ThemedMessageDialog.warning(self, self.i18n.t("warning"), self.i18n.t("stop_not_loading"))
            self._clear_input_selection_after_dialog(self.btn_stop)
            return

        self.btn_stop.setEnabled(False)
        if self._loading_game_list and not self.btn_fetch.isEnabled():
            self._stopped_during_game_list_loading = True
        self.cancel_event.set()

    def _on_game_list_loading_started(self):
        if not self.cancel_event.is_set() and self._loading_game_list:
            self._set_status("loading_games")

    def _on_games_list_ready(self, api_key: str, steamid64: str, games: List[Dict]):
        self._loading_game_list = False
        if self.cancel_event.is_set():
            self._finalize_loading(stopped=True)
            return

        self.current_steamid = steamid64
        self._load_user_analysis_cache(steamid64)
        self.total_games = len(games)
        if self.total_games == 0:
            self._finalize_loading(completed=False)
            self.progress.setValue(0)
            self._set_status("no_games_status")
            ThemedMessageDialog.information(self, self.i18n.t("info"), self.i18n.t("no_games"))
            self._clear_input_selection_after_dialog()
            return

        self._set_status("found_games", n=self.total_games)

        self.games_index = {g["appid"]: g["name"] for g in games}
        self.cmb_game.blockSignals(True)
        self.cmb_game.clear()
        self.cmb_game.addItem(self.i18n.t("all_games"), userData=None)
        for appid, name in sorted(self.games_index.items(), key=lambda x: x[1].lower()):
            self.cmb_game.addItem(name, userData=appid)
        self.cmb_game.setEnabled(self.cmb_game.count() > 1)
        self.cmb_game.blockSignals(False)

        self._game_queue = deque(games)
        self._active_workers = 0
        self._start_next_jobs()

    def _start_next_jobs(self):
        while (not self.cancel_event.is_set()) and self._game_queue and (self._active_workers < self.max_workers):
            g = self._game_queue.popleft()
            worker = GameFetchWorker(self.current_api_key, self.current_steamid, g, self.cancel_event, self.i18n.lang)
            self._workers.append(worker)

            worker.signals.partial.connect(self._on_game_partial)
            worker.signals.error.connect(lambda msg, w=worker: self._on_game_fetch_error(msg))
            worker.signals.done.connect(lambda w=worker: (self._safe_remove_worker(w), self._on_game_done()))

            self._active_workers += 1
            self.threadpool.start(worker)

    def _on_game_done(self):
        self.loaded_games += 1
        self._active_workers = max(0, self._active_workers - 1)
        if not self._load_error_reported:
            self._update_progress_label()

        if not self.cancel_event.is_set() and self._game_queue:
            self._start_next_jobs()

        if self.loaded_games >= self.total_games and not self._load_error_reported:
            self._finalize_loading(completed=True)
            return

        if self.cancel_event.is_set() and self._active_workers == 0:
            if self._load_error_reported:
                self._finalize_loading(completed=False)
                self._set_status("error")
            else:
                self._finalize_loading(completed=False, stopped=True)

    def _achievement_exact_key(self, a: Achievement) -> tuple:
        if a.appid and a.apiname:
            return ("exact", int(a.appid), str(a.apiname).strip().lower(), int(a.unlock_time or 0))
        return self._achievement_loose_key(a)

    def _achievement_loose_key(self, a: Achievement) -> tuple:
        return (
            "loose",
            str(a.game_name or "").strip().lower(),
            str(self._achievement_display_name(a) or a.apiname or "").strip().lower(),
            int(a.unlock_time or 0),
        )

    def _merge_achievements(self, achs: List[Achievement]) -> int:
        added = 0
        for a in achs:
            exact_key = self._achievement_exact_key(a)
            loose_key = self._achievement_loose_key(a)
            if exact_key in self._achievement_keys or loose_key in self._achievement_loose_keys:
                continue
            self.achievements.append(a)
            self._achievement_keys.add(exact_key)
            self._achievement_loose_keys.add(loose_key)
            added += 1
        if added:
            self._analysis_cache_signature = None
        return added

    def _load_user_analysis_cache(self, steamid64: str) -> None:
        cached = read_user_achievements(steamid64)
        if not cached:
            return
        added = self._merge_achievements(cached)
        if added:
            self.refresh_table(update_status=False)

    def _on_game_partial(self, achs: List[Achievement]):
        if achs:
            added = self._merge_achievements(achs)
            if added and not self.refresh_timer.isActive():
                self.refresh_timer.start()
            if self.icons_enabled and not self.cancel_event.is_set():
                self._schedule_visible_icon_load()

    def _finalize_loading(self, completed: bool = False, stopped: bool = False):
        self._export_blocked_until_ready = False
        self._loading_game_list = False
        self.btn_fetch.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.cmb_game.setEnabled(self.cmb_game.count() > 1)

        done = min(self.loaded_games, self.total_games) if self.total_games else 0
        pct = int(100 * done / max(1, self.total_games))

        if self.refresh_timer.isActive():
            self.refresh_timer.stop()

        self.refresh_table(update_status=False)
        if self.current_steamid and self.achievements:
            write_user_achievements(self.current_steamid, self.achievements)
            self._update_cache_button_text(force=True)

        if completed:
            self.progress.setValue(100)
        elif stopped and self._stopped_during_game_list_loading:
            self.progress.setValue(0)
        elif stopped:
            self.progress.setValue(100)
        else:
            self.progress.setValue(pct)

        if stopped:
            if self._stopped_during_game_list_loading:
                self._set_status("stop")
            else:
                self._set_status("stopped_processed", done=done, total=self.total_games, ach=len(self.achievements))
            self._stopped_during_game_list_loading = False
        elif completed:
            self._set_status("ready_shown", n=self.table.rowCount())

    def _update_progress_label(self):
        done = min(self.loaded_games, self.total_games) if self.total_games else 0
        pct = int(100 * done / max(1, self.total_games))
        self.progress.setValue(pct)
        self._set_status("processed", done=done, total=self.total_games, ach=len(self.achievements))

    def _normalize_error_message(self, message: str) -> tuple[str, bool]:
        text = str(message or "")
        if text.startswith(UNKNOWN_ERROR_PREFIX):
            return text[len(UNKNOWN_ERROR_PREFIX):], True
        return text, False

    def _on_game_fetch_error(self, message: str):
        if self._load_error_reported or not self._export_blocked_until_ready:
            return
        if self.cancel_event.is_set():
            return
        self._load_error_reported = True
        self.cancel_event.set()
        self._game_queue.clear()
        self._stop_icon_downloads()
        self._set_status("error")
        message, show_copy = self._normalize_error_message(message)
        ThemedMessageDialog.critical(self, self.i18n.t("error"), message, show_copy=show_copy)

    def _on_game_list_error(self, message: str):
        if self.cancel_event.is_set() and not self._load_error_reported:
            self._loading_game_list = False
            self._finalize_loading(stopped=True)
            return
        self.on_error(message)

    def on_error(self, message: str):
        if self.cancel_event.is_set() and not self._load_error_reported:
            self._loading_game_list = False
            self._finalize_loading(stopped=True)
            return
        self._load_error_reported = True
        self.cancel_event.set()
        self._game_queue.clear()
        self._stop_icon_downloads()
        self._loading_game_list = False
        self._finalize_loading()
        self._set_status("error")
        message, show_copy = self._normalize_error_message(message)
        ThemedMessageDialog.critical(self, self.i18n.t("error"), message, show_copy=show_copy)