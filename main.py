#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
import re
import time
import csv
import threading
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import requests
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

API_BASE = "https://api.steampowered.com"
HEADERS = {"User-Agent": "SteamAchievementInspector/3.2 (+https://github.com/yourname/SteamAchievementInspector)"}


class InvalidAPIKeyError(PermissionError):
    pass


class I18n:
    def __init__(self, lang: str = "en"):
        self.lang = lang
        self._t = {
            "en": {
                "app_title": "Steam Achievement Inspector",
                "profile": "Profile",
                "profile_ph": "Steam profile URL (or steamid64/vanity)",
                "api_key": "API Key",
                "api_key_ph": "Steam Web API Key (32 hex)",
                "api_invalid": "Invalid Steam Web API key or not authorized. "
                               "Double-check the key on https://steamcommunity.com/dev/apikey and try again.",
                "language": "Language",
                "load": "Load",
                "stop": "Stop",
                "game": "Game",
                "sort_desc": "By time: desc",
                "sort_asc": "By time: asc",
                "n_label": "N (Δt) =",
                "only_susp": "Only suspicious (≤ N min)",
                "only_exact": "Only identical timestamps",
                "reset": "Reset filters",
                "file_menu": "File",
                "export_csv": "Export CSV…",
                "ready": "Ready.",
                "loading_games": "Loading game list…",
                "found_games": "Found games: {n}. Starting to load achievements…",
                "processed": "[{done}/{total}] games processed • Achievements collected: {ach}",
                "shown": "Shown: {n}",
                "enter_profile": "Enter a profile URL / steamid / vanity.",
                "enter_key": "Enter a Steam Web API Key.",
                "key_warn": "Key does not look like a 32-hex token. Please check and try again.",
                "error": "Error",
                "warning": "Warning",
                "info": "Info",
                "export_none": "Nothing to export.",
                "save_csv": "Save CSV",
                "export_done": "Done!",
                "hdr_icon": "Icon",
                "hdr_game": "Game",
                "hdr_ach": "Achievement",
                "hdr_desc": "Description",
                "hdr_time": "Time",
                "hdr_delta": "Δt",
                "hdr_flag": "⚠",
                "all_games": "All games",
                "dash": "—",
                "secs_fmt": "{s}s",
                "mins_secs_fmt": "{m}m {s:02d}s",
                "susp_yes": "YES",
                "thr_exact": "exact (0s)",
                "thr_leq": "≤ {n} min",
            },
            "ru": {
                "app_title": "Steam Achievement Inspector",
                "profile": "Профиль",
                "profile_ph": "URL профиля Steam (или steamid64/vanity)",
                "api_key": "API Key",
                "api_key_ph": "Steam Web API Key (32 hex)",
                "api_invalid": "Неверный Steam Web API ключ или нет доступа. "
                               "Проверьте ключ на https://steamcommunity.com/dev/apikey и попробуйте снова.",
                "language": "Язык",
                "load": "Загрузить",
                "stop": "Стоп",
                "game": "Игра",
                "sort_desc": "По времени: убыв.",
                "sort_asc": "По времени: возр.",
                "n_label": "N (Δt) =",
                "only_susp": "Только подозрительные (≤ N мин)",
                "only_exact": "Только одинаковые таймстампы",
                "reset": "Сброс фильтров",
                "file_menu": "Файл",
                "export_csv": "Экспорт CSV…",
                "ready": "Готово.",
                "loading_games": "Загрузка списка игр…",
                "found_games": "Нашли игр: {n}. Загрузка достижений…",
                "processed": "[{done}/{total}] игр обработано • Достижений собрано: {ach}",
                "shown": "Показано: {n}",
                "enter_profile": "Введите URL профиля/steamid/vanity.",
                "enter_key": "Введите Steam Web API Key.",
                "key_warn": "Ключ не похож на 32-символьный hex. Проверьте и попробуйте снова.",
                "error": "Ошибка",
                "warning": "Внимание",
                "info": "Информация",
                "export_none": "Нечего экспортировать.",
                "save_csv": "Сохранить CSV",
                "export_done": "Готово!",
                "hdr_icon": "Иконка",
                "hdr_game": "Игра",
                "hdr_ach": "Достижение",
                "hdr_desc": "Описание",
                "hdr_time": "Время",
                "hdr_delta": "Δt",
                "hdr_flag": "⚠",
                "all_games": "Все игры",
                "dash": "—",
                "secs_fmt": "{s}с",
                "mins_secs_fmt": "{m}м {s:02d}с",
                "susp_yes": "YES",
                "thr_exact": "ровно 0с",
                "thr_leq": "≤ {n} мин",
            },
        }

    def set_lang(self, lang: str):
        self.lang = "en" if lang not in ("en", "ru") else lang

    def t(self, key: str) -> str:
        return self._t[self.lang].get(key, key)

    def fmt(self, key: str, **kw) -> str:
        return self.t(key).format(**kw)


@dataclass
class Achievement:
    appid: int
    game_name: str
    apiname: str
    name: str
    description: str
    icon_url: str
    unlocked: bool
    unlock_time: int  

    def unlock_dt(self) -> Optional[datetime]:
        if self.unlock_time and self.unlock_time > 0:
            return datetime.fromtimestamp(self.unlock_time)
        return None


class SteamAPI:
    def __init__(self, api_key: str, lang: str = "en", timeout: int = 25):
        self.api_key = api_key
        self.lang = lang
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get(self, url: str, params: Dict) -> Dict:
        for attempt in range(3):
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (401, 403):
                    raise InvalidAPIKeyError(f"HTTP {r.status_code}")
                time.sleep(0.5 * (attempt + 1))
            except requests.RequestException:
                time.sleep(0.5 * (attempt + 1))
        r = self.session.get(url, params=params, timeout=self.timeout)
        if r.status_code in (401, 403):
            raise InvalidAPIKeyError(f"HTTP {r.status_code}")
        r.raise_for_status()
        return r.json()

    @staticmethod
    def looks_like_valid_key_format(key: str) -> bool:
        return bool(re.fullmatch(r"[A-Fa-f0-9]{32}", key))

    def resolve_steamid64(self, profile_url: str) -> str:
        u = profile_url.strip().rstrip("/")
        if re.fullmatch(r"\d{17}", u):
            return u
        m = re.search(r"/profiles/(\d{17})", u)
        if m:
            return m.group(1)
        vanity = None
        m = re.search(r"/id/([^/?#]+)", u)
        if m:
            vanity = m.group(1)
        elif re.fullmatch(r"[A-Za-z0-9_\-\.]+", u):
            vanity = u
        if vanity:
            url = f"{API_BASE}/ISteamUser/ResolveVanityURL/v0001/"
            data = self._get(url, {"key": self.api_key, "vanityurl": vanity})
            if data and data.get("response", {}).get("success") == 1:
                return data["response"]["steamid"]
            raise ValueError("Failed to resolve vanity to steamid64.")
        raise ValueError("Enter valid Steam profile URL or steamid64/vanity.")

    def verify_key_can_read_profile(self, steamid64: str) -> None:
        url = f"{API_BASE}/ISteamUser/GetPlayerSummaries/v0002/"
        _ = self._get(url, {"key": self.api_key, "steamids": steamid64})

    def get_player_achievements_full(self, steamid64: str, appid: int) -> Tuple[List[Dict], Optional[str]]:
        url = f"{API_BASE}/ISteamUserStats/GetPlayerAchievements/v0001/"
        params = {"key": self.api_key, "steamid": steamid64, "appid": appid, "l": self.lang}
        data = self._get(url, params)
        ps = data.get("playerstats", {})
        reason: Optional[str] = None
        if ps.get("success") is False:
            reason = ps.get("error") or "no stats or private"
            return [], reason
        ach = ps.get("achievements", [])
        res = []
        for a in ach or []:
            if bool(a.get("achieved", 0)):
                res.append({"apiname": a.get("apiname", ""), "unlocktime": int(a.get("unlocktime", 0) or 0)})
        if (not res) and ach:
            reason = "no unlocked achievements"
        return res, reason

    def get_schema_for_game(self, appid: int) -> Dict[str, Dict[str, str]]:
        url = f"{API_BASE}/ISteamUserStats/GetSchemaForGame/v2/"
        params = {"key": self.api_key, "appid": appid, "l": self.lang}
        data = self._get(url, params)
        game = data.get("game", {})
        stats = game.get("availableGameStats", {}) or {}
        ach = stats.get("achievements", []) or []
        mapping: Dict[str, Dict[str, str]] = {}
        for a in ach:
            apiname = a.get("name", "")
            if not apiname:
                continue
            mapping[apiname] = {
                "displayName": a.get("displayName", apiname),
                "description": a.get("description", "") or "",
                "icon": a.get("icon", "") or "",
                "icongray": a.get("icongray", "") or "",
            }
        return mapping

    def get_owned_games(self, steamid64: str) -> List[Dict]:
        url = f"{API_BASE}/IPlayerService/GetOwnedGames/v0001/"
        params = {
            "key": self.api_key,
            "steamid": steamid64,
            "include_appinfo": 1,
            "include_played_free_games": 1,
            "format": "json",
        }
        data = self._get(url, params)
        games = data.get("response", {}).get("games", []) or []
        norm = []
        for g in games:
            appid = g.get("appid")
            name = g.get("name") or f"App {appid}"
            pt = int(g.get("playtime_forever") or 0)
            if appid:
                norm.append({"appid": appid, "name": name, "playtime": pt})
        norm.sort(key=lambda x: (-x["playtime"], x["name"].lower()))
        return norm


class NoHighlightDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex):
        opt = QtWidgets.QStyleOptionViewItem(option)
        State = getattr(QtWidgets.QStyle, "StateFlag", QtWidgets.QStyle)  
        opt.state &= ~State.State_Selected
        opt.state &= ~State.State_MouseOver
        opt.state &= ~State.State_HasFocus
        super().paint(painter, opt, index)


class QuietTable(QtWidgets.QTableWidget):
    def wheelEvent(self, e: QtGui.QWheelEvent) -> None:
        super().wheelEvent(e)                
        QtCore.QTimer.singleShot(0, self._clear_current)

    def _clear_current(self):
        try:
            self.selectionModel().clearSelection()
        except Exception:
            pass
        self.setCurrentIndex(QtCore.QModelIndex())
        self.clearFocus()


class ListGamesWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        finished = QtCore.pyqtSignal(str, list)   
        error = QtCore.pyqtSignal(str)

    def __init__(self, api_key: str, profile_url: str, lang: str):
        super().__init__()
        self.api_key = api_key
        self.profile_url = profile_url
        self.lang = lang
        self.signals = ListGamesWorker.Signals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            api = SteamAPI(self.api_key, self.lang)
            steamid64 = api.resolve_steamid64(self.profile_url)
            api.verify_key_can_read_profile(steamid64)
            games = api.get_owned_games(steamid64)
            self.signals.finished.emit(steamid64, games)
        except InvalidAPIKeyError:
            i18n = I18n(self.lang)
            self.signals.error.emit(i18n.t("api_invalid"))
        except Exception as e:
            self.signals.error.emit(str(e))


class GameFetchWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        partial = QtCore.pyqtSignal(list)                    
        skipped = QtCore.pyqtSignal(dict, str)               
        done = QtCore.pyqtSignal()
        error = QtCore.pyqtSignal(str)

    def __init__(self, api_key: str, lang: str, steamid64: str, game: Dict, cancel_event: threading.Event):
        super().__init__()
        self.api_key = api_key
        self.lang = lang
        self.steamid64 = steamid64
        self.game = game
        self.cancel_event = cancel_event
        self.signals = GameFetchWorker.Signals()

    @QtCore.pyqtSlot()
    def run(self):
        if self.cancel_event.is_set():
            self.signals.done.emit()
            return
        try:
            api = SteamAPI(self.api_key, self.lang)
            appid = int(self.game["appid"])
            gname = self.game["name"]

            pa, reason = api.get_player_achievements_full(self.steamid64, appid)
            achs: List[Achievement] = []
            if pa:
                schema = api.get_schema_for_game(appid)
                for a in pa:
                    meta = schema.get(a["apiname"], {})
                    achs.append(
                        Achievement(
                            appid=appid,
                            game_name=gname,
                            apiname=a["apiname"],
                            name=meta.get("displayName", a["apiname"]),
                            description=meta.get("description", ""),
                            icon_url=meta.get("icon", ""),
                            unlocked=True,
                            unlock_time=int(a["unlocktime"]),
                        )
                    )
                self.signals.partial.emit(achs)
            else:
                if reason and reason not in ("no unlocked achievements",):
                    self.signals.skipped.emit(self.game, reason)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.done.emit()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.i18n = I18n("en")

        self.setWindowTitle(self.i18n.t("app_title"))
        self.resize(1250, 780)

        self.achievements: List[Achievement] = []
        self.games_index: Dict[int, str] = {}
        self.total_games: int = 0
        self.loaded_games: int = 0
        self.cancel_event = threading.Event()

        self._workers: List[QtCore.QRunnable] = []

        cpu = os.cpu_count() or 4
        self.max_workers: int = min(8, max(4, cpu))
        self._game_queue: deque[Dict] = deque()
        self._active_workers: int = 0
        self.current_api_key = ""
        self.current_lang = "en"
        self.current_steamid = ""
        self.current_profile_url = ""

        self.threadpool = QtCore.QThreadPool.globalInstance()
        self.threadpool.setMaxThreadCount(self.max_workers)

        self.icon_cache: Dict[str, QtGui.QIcon] = {}
        self.icon_downloading: Set[str] = set()
        self.net = QNetworkAccessManager(self)
        self.net.finished.connect(self._on_icon_loaded)
        self._pending_icon_urls: Set[str] = set()

        self.refresh_timer = QtCore.QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(150)
        self.refresh_timer.timeout.connect(self.refresh_table)

        self.issues: List[Tuple[str, str]] = []

        self._build_ui()
        self._retranslate_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)

        # Top row
        top = QtWidgets.QHBoxLayout()
        v.addLayout(top)

        self.lbl_profile = QtWidgets.QLabel()
        self.edt_profile = QtWidgets.QLineEdit()
        self.edt_profile.setMinimumWidth(380)

        self.lbl_api = QtWidgets.QLabel()
        self.edt_key = QtWidgets.QLineEdit()
        self.edt_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

        self.lbl_lang = QtWidgets.QLabel()
        self.cmb_lang = QtWidgets.QComboBox()
        self.cmb_lang.addItem("English", userData="en")
        self.cmb_lang.addItem("Русский", userData="ru")
        self.cmb_lang.setCurrentIndex(0)
        self.cmb_lang.currentIndexChanged.connect(self.on_ui_lang_changed)

        self.btn_fetch = QtWidgets.QPushButton()
        self.btn_fetch.clicked.connect(self.on_fetch)

        self.btn_stop = QtWidgets.QPushButton()
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.on_stop)

        top.addWidget(self.lbl_profile)
        top.addWidget(self.edt_profile, 2)
        top.addWidget(self.lbl_api)
        top.addWidget(self.edt_key, 1)
        top.addWidget(self.lbl_lang)
        top.addWidget(self.cmb_lang)
        top.addWidget(self.btn_fetch)
        top.addWidget(self.btn_stop)

        filters = QtWidgets.QHBoxLayout()
        v.addLayout(filters)

        self.lbl_game = QtWidgets.QLabel()
        self.cmb_game = QtWidgets.QComboBox()
        self.cmb_game.addItem("", userData=None)
        self.cmb_game.currentIndexChanged.connect(self.refresh_table)

        self.cmb_sort = QtWidgets.QComboBox()
        self.cmb_sort.currentIndexChanged.connect(self.refresh_table)

        self.lbl_n = QtWidgets.QLabel()
        self.spin_n = QtWidgets.QSpinBox()
        self.spin_n.setRange(0, 120)
        self.spin_n.setValue(2)
        self.spin_n.valueChanged.connect(self.refresh_table)

        self.chk_only_susp = QtWidgets.QCheckBox()
        self.chk_only_susp.stateChanged.connect(self.refresh_table)

        self.chk_only_exact = QtWidgets.QCheckBox()
        self.chk_only_exact.stateChanged.connect(self.refresh_table)

        self.btn_reset = QtWidgets.QPushButton()
        self.btn_reset.clicked.connect(self.reset_filters)

        filters.addWidget(self.lbl_game)
        filters.addWidget(self.cmb_game, 2)
        filters.addWidget(self.cmb_sort)
        filters.addSpacing(12)
        filters.addWidget(self.lbl_n)
        filters.addWidget(self.spin_n)
        filters.addWidget(self.chk_only_susp)
        filters.addWidget(self.chk_only_exact)
        filters.addStretch()
        filters.addWidget(self.btn_reset)

        # Table
        self.table = QuietTable(0, 7)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setIconSize(QtCore.QSize(32, 32))
        self.table.setStyleSheet("QTableWidget::item:selected{ background: palette(base); color: palette(text); }")
        self.table.setItemDelegate(NoHighlightDelegate(self.table))
        self.table.viewport().installEventFilter(self)

        hh = self.table.horizontalHeader()
        hh.setDefaultSectionSize(200)
        hh.setMinimumSectionSize(40)
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)       
        self.table.setColumnWidth(0, 70)  
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Interactive) 
        self.table.setColumnWidth(1, 220)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Interactive) 
        self.table.setColumnWidth(2, 260)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)     
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(4, 170)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Interactive) 
        self.table.setColumnWidth(5, 90)
        hh.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Fixed)    
        self.table.setColumnWidth(6, 40)

        v.addWidget(self.table, 1)

        bottom = QtWidgets.QHBoxLayout()
        v.addLayout(bottom)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.lbl_status = QtWidgets.QLabel()
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.lbl_status)

        self.link = QtWidgets.QLabel('<a href="https://steamcommunity.com/id/sqwirex/">My Steam</a>')
        self.link.setOpenExternalLinks(True)
        self.link.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.link.setStyleSheet("QLabel{ padding-left:10px; }")
        bottom.addWidget(self.link)

        # Menu export
        self.action_export = QtGui.QAction(self)
        self.action_export.triggered.connect(self.export_csv)
        self.menu_file = self.menuBar().addMenu("")
        self.menu_file.addAction(self.action_export)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self.table.viewport():
            if event.type() in (
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QEvent.Type.MouseButtonRelease,
                QtCore.QEvent.Type.MouseButtonDblClick,
                QtCore.QEvent.Type.MouseMove,
            ):
                return True
        return super().eventFilter(obj, event)

    def _retranslate_ui(self):
        t = self.i18n.t
        self.setWindowTitle(t("app_title"))
        self.lbl_profile.setText(t("profile") + ":")
        self.edt_profile.setPlaceholderText(t("profile_ph"))
        self.lbl_api.setText(t("api_key") + ":")
        self.edt_key.setPlaceholderText(t("api_key_ph"))
        self.lbl_lang.setText(t("language") + ":")
        self.btn_fetch.setText(t("load"))
        self.btn_stop.setText(t("stop"))
        self.lbl_game.setText(t("game") + ":")
        self.cmb_sort.blockSignals(True)
        self.cmb_sort.clear()
        self.cmb_sort.addItems([t("sort_desc"), t("sort_asc")])
        self.cmb_sort.blockSignals(False)
        self.lbl_n.setText(t("n_label"))
        self.spin_n.setSuffix(" min" if self.i18n.lang == "en" else " мин")
        self.chk_only_susp.setText(t("only_susp"))
        self.chk_only_exact.setText(t("only_exact"))
        self.btn_reset.setText(t("reset"))
        self.table.setHorizontalHeaderLabels(
            [t("hdr_icon"), t("hdr_game"), t("hdr_ach"), t("hdr_desc"), t("hdr_time"), t("hdr_delta"), t("hdr_flag")]
        )
        self.menu_file.setTitle(t("file_menu"))
        self.action_export.setText(t("export_csv"))
        self.lbl_status.setText(t("ready"))
        self.cmb_game.blockSignals(True)
        if self.cmb_game.count() == 0:
            self.cmb_game.addItem(t("all_games"), userData=None)
        else:
            self.cmb_game.setItemText(0, t("all_games"))
        self.cmb_game.blockSignals(False)

    def on_ui_lang_changed(self):
        lang = self.cmb_lang.currentData() or "en"
        self.i18n.set_lang(lang)
        self._retranslate_ui()

    def on_fetch(self):
        url = self.edt_profile.text().strip()
        key = self.edt_key.text().strip()
        lang = self.cmb_lang.currentData() or "en"

        if not url:
            QtWidgets.QMessageBox.warning(self, self.i18n.t("warning"), self.i18n.t("enter_profile"))
            return
        if not key:
            QtWidgets.QMessageBox.warning(self, self.i18n.t("warning"), self.i18n.t("enter_key"))
            return
        if not SteamAPI.looks_like_valid_key_format(key):
            QtWidgets.QMessageBox.warning(self, self.i18n.t("warning"), self.i18n.t("key_warn"))
            return  

        self.cancel_event.clear()
        self.btn_fetch.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress.setValue(0)
        self.achievements.clear()
        self.loaded_games = 0
        self.games_index.clear()
        self._game_queue.clear()
        self._active_workers = 0
        self.issues.clear()
        self._workers.clear()

        self.cmb_game.blockSignals(True)
        self.cmb_game.clear()
        self.cmb_game.addItem(self.i18n.t("all_games"), userData=None)
        self.cmb_game.blockSignals(False)
        self.table.setRowCount(0)
        self.icon_cache.clear()
        self.icon_downloading.clear()
        self._pending_icon_urls.clear()
        self.lbl_status.setText(self.i18n.t("loading_games"))

        self.current_api_key = key
        self.current_lang = lang
        self.current_profile_url = url

        lgw = ListGamesWorker(key, url, lang)
        self._workers.append(lgw)
        lgw.signals.finished.connect(
            lambda steamid64, games, w=lgw: (self._safe_remove_worker(w),
                                             self._on_games_list_ready(key, lang, steamid64, games))
        )
        lgw.signals.error.connect(
            lambda msg, w=lgw: (self._safe_remove_worker(w), self.on_error(msg))
        )
        self.threadpool.start(lgw)

    def _safe_remove_worker(self, w: QtCore.QRunnable):
        try:
            self._workers.remove(w)
        except ValueError:
            pass

    def on_stop(self):
        self.cancel_event.set()
        self.btn_stop.setEnabled(False)

    def _on_games_list_ready(self, api_key: str, lang: str, steamid64: str, games: List[Dict]):
        if self.cancel_event.is_set():
            self._finalize_loading()
            return

        self.current_steamid = steamid64
        self.total_games = len(games)
        self.lbl_status.setText(self.i18n.fmt("found_games", n=self.total_games))

        self.games_index = {g["appid"]: g["name"] for g in games}
        self.cmb_game.blockSignals(True)
        self.cmb_game.clear()
        self.cmb_game.addItem(self.i18n.t("all_games"), userData=None)
        for appid, name in sorted(self.games_index.items(), key=lambda x: x[1].lower()):
            self.cmb_game.addItem(name, userData=appid)
        self.cmb_game.blockSignals(False)

        self._game_queue = deque(games)
        self._active_workers = 0
        self._start_next_jobs()

    def _start_next_jobs(self):
        while (not self.cancel_event.is_set()) and self._game_queue and (self._active_workers < self.max_workers):
            g = self._game_queue.popleft()
            worker = GameFetchWorker(self.current_api_key, self.current_lang, self.current_steamid, g, self.cancel_event)
            self._workers.append(worker)

            worker.signals.partial.connect(self._on_game_partial)
            worker.signals.skipped.connect(self._on_game_skipped)
            worker.signals.error.connect(lambda _msg, w=worker: self._safe_remove_worker(w))
            worker.signals.done.connect(lambda w=worker: (self._safe_remove_worker(w), self._on_game_done()))

            self._active_workers += 1
            self.threadpool.start(worker)

    def _on_game_skipped(self, game: Dict, reason: str):
        self.issues.append((game.get("name", f"App {game.get('appid')}"), reason))

    def _on_game_done(self):
        self.loaded_games += 1
        self._active_workers = max(0, self._active_workers - 1)
        self._update_progress_label()
        if not self.cancel_event.is_set() and self._game_queue:
            self._start_next_jobs()
        if self.loaded_games >= self.total_games or self.cancel_event.is_set():
            self._finalize_loading()

    def _on_game_partial(self, achs: List[Achievement]):
        if self.cancel_event.is_set():
            return
        if achs:
            self.achievements.extend(achs)
            for a in achs:
                if a.icon_url and (a.icon_url not in self.icon_cache) and (a.icon_url not in self.icon_downloading):
                    self._pending_icon_urls.add(a.icon_url)
            self._kick_icon_prefetch()
            if not self.refresh_timer.isActive():
                self.refresh_timer.start()

    def _kick_icon_prefetch(self):
        while self._pending_icon_urls and len(self.icon_downloading) < 8:
            url = self._pending_icon_urls.pop()
            self.icon_downloading.add(url)
            req = QNetworkRequest(QtCore.QUrl(url))
            self.net.get(req)

    def _on_icon_loaded(self, reply: QNetworkReply):
        url = reply.url().toString()
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll().data()
                pix = QtGui.QPixmap()
                if pix.loadFromData(data):
                    self.icon_cache[url] = QtGui.QIcon(pix)
        finally:
            reply.deleteLater()
            self.icon_downloading.discard(url)
            if not self.refresh_timer.isActive():
                self.refresh_timer.start()
            self._kick_icon_prefetch()

    def _finalize_loading(self):
        self.btn_fetch.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress.setValue(100)

    def _update_progress_label(self):
        done = min(self.loaded_games, self.total_games) if self.total_games else 0
        pct = int(100 * done / max(1, self.total_games))
        self.progress.setValue(pct)
        self.lbl_status.setText(self.i18n.fmt("processed", done=done, total=self.total_games, ach=len(self.achievements)))

    def on_error(self, message: str):
        self._finalize_loading()
        QtWidgets.QMessageBox.critical(self, self.i18n.t("error"), message)

    def _filtered_sorted(self) -> List[Achievement]:
        items = self.achievements[:]
        appid = self.cmb_game.currentData()
        if appid:
            items = [a for a in items if a.appid == appid]

        asc = (self.cmb_sort.currentIndex() == 1)
        items.sort(key=lambda a: (a.unlock_time or 0, a.game_name, a.name), reverse=not asc)

        n_minutes = self.spin_n.value()
        exact_on = self.chk_only_exact.isChecked()
        susp_on  = self.chk_only_susp.isChecked()

        if exact_on and susp_on:
            within = self._filter_within_n(items, n_minutes)
            exact  = self._filter_exact_timestamp(items)
            want_ids = {id(x) for x in within} | {id(x) for x in exact}
            return [x for x in items if id(x) in want_ids]

        if exact_on:
            return self._filter_exact_timestamp(items)

        if susp_on:
            return self._filter_within_n(items, n_minutes)

        return items


    def _filter_within_n(self, items: List[Achievement], n_minutes: int) -> List[Achievement]:
        if n_minutes <= 0 or len(items) < 2:
            return []
        n_sec = n_minutes * 60
        marked = set()
        for i in range(len(items) - 1):
            a, b = items[i], items[i + 1]
            if not (a.unlock_time and b.unlock_time):
                continue
            diff = abs(b.unlock_time - a.unlock_time)
            if 0 < diff <= n_sec:
                marked.add(i); marked.add(i + 1)
        return [items[i] for i in sorted(marked)]



    def _filter_exact_timestamp(self, items: List[Achievement]) -> List[Achievement]:
        by_ts: Dict[int, List[int]] = {}
        for i, a in enumerate(items):
            if a.unlock_time:
                by_ts.setdefault(a.unlock_time, []).append(i)
        keep_idx = []
        for _, idxs in by_ts.items():
            if len(idxs) >= 2:
                keep_idx.extend(idxs)
        keep_idx = sorted(set(keep_idx))
        return [items[i] for i in keep_idx]

    def refresh_table(self):
        t = self.i18n
        items = self._filtered_sorted()
        self.table.setRowCount(0)

        exact_count: Dict[int, int] = {}
        for a in items:
            if a.unlock_time:
                exact_count[a.unlock_time] = exact_count.get(a.unlock_time, 0) + 1

        prev_ts: Optional[int] = None
        n_sec_threshold = self.spin_n.value() * 60
        warn_color = QtGui.QColor("#f59f00")

        for a in items:
            row = self.table.rowCount()
            self.table.insertRow(row)

            icon_item = QtWidgets.QTableWidgetItem()
            ic = self.icon_cache.get(a.icon_url)
            if ic:
                icon_item.setIcon(ic)
            self.table.setItem(row, 0, icon_item)

            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(a.game_name))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(a.name or a.apiname))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(a.description or ""))

            dt = a.unlock_dt()
            ts_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else t.t("dash")
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(ts_str))

            if prev_ts is None or not a.unlock_time:
                delta_str = t.t("dash"); delta_ok = False
            else:
                d = abs(a.unlock_time - prev_ts)
                mins = d // 60; secs = d % 60
                delta_str = (t.fmt("mins_secs_fmt", m=mins, s=secs) if mins > 0
                             else t.fmt("secs_fmt", s=secs))
                delta_ok = d <= max(1, n_sec_threshold)
            prev_ts = a.unlock_time or prev_ts
            delta_item = QtWidgets.QTableWidgetItem(delta_str)
            self.table.setItem(row, 5, delta_item)

            is_exact_dup = bool(a.unlock_time and exact_count.get(a.unlock_time, 0) >= 2)
            suspicious = is_exact_dup or (delta_str != t.t("dash") and delta_ok)

            flag_item = QtWidgets.QTableWidgetItem("⚠" if suspicious else "")
            flag_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if suspicious:
                flag_item.setForeground(QtGui.QBrush(warn_color))
                f = delta_item.font()
                f.setBold(True)
                delta_item.setFont(f)
            self.table.setItem(row, 6, flag_item)

        self.table.resizeRowsToContents()
        self.lbl_status.setText(t.fmt("shown", n=self.table.rowCount()))

    def reset_filters(self):
        self.cmb_game.setCurrentIndex(0)
        self.cmb_sort.setCurrentIndex(0)
        self.spin_n.setValue(2)
        self.chk_only_susp.setChecked(False)
        self.chk_only_exact.setChecked(False)
        self.refresh_table()

    def _threshold_label(self) -> str:
        if self.chk_only_exact.isChecked():
            return self.i18n.t("thr_exact")
        n = self.spin_n.value()
        return self.i18n.fmt("thr_leq", n=n)

    def export_csv(self):
        t = self.i18n.t
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, t("info"), t("export_none"))
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("save_csv"),
                                                        "achievements.csv", "CSV (*.csv)")
        if not path:
            return

        exported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game_filter = self.cmb_game.currentText() or t("all_games")
        sort_label = self.cmb_sort.currentText()
        threshold_text = self._threshold_label()  # only in metadata
        only_susp = "on" if self.chk_only_susp.isChecked() else "off"
        only_exact = "on" if self.chk_only_exact.isChecked() else "off"

        def write_csv(to_path: str):
            with open(to_path, "w", newline="", encoding="utf-8-sig") as f:
                f.write("sep=;\n")
                f.write("# Steam Achievement Inspector export\n")
                f.write(f"# Exported: {exported_at}\n")
                f.write(f"# Profile: {self.current_profile_url}\n")
                f.write(f"# UI language: {self.i18n.lang}\n")
                f.write(f"# Game filter: {game_filter}\n")
                f.write(f"# Sort: {sort_label}\n")
                f.write(f"# Threshold: {threshold_text}\n")
                f.write(f"# Only suspicious filter: {only_susp}\n")
                f.write(f"# Only exact filter: {only_exact}\n")

                w = csv.writer(f, delimiter=";")
                w.writerow([t("hdr_game"), t("hdr_ach"), t("hdr_desc"),
                            t("hdr_time"), t("hdr_delta"), "Suspicious"])
                for r in range(self.table.rowCount()):
                    def text(c):
                        it = self.table.item(r, c)
                        return it.text() if it else ""
                    w.writerow([text(1), text(2), text(3), text(4), text(5),
                                (t("susp_yes") if text(6) else "")])

        try:
            write_csv(path)
        except PermissionError:
            base, ext = os.path.splitext(path)
            alt = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext or '.csv'}"
            QtWidgets.QMessageBox.warning(
                self, self.i18n.t("error"),
                "Can't write the file (permission denied). Close it in Excel or choose another path."
            )
            new_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("save_csv"), alt, "CSV (*.csv)")
            if new_path:
                write_csv(new_path)
            else:
                return

        QtWidgets.QMessageBox.information(self, t("info"), t("export_done"))


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
