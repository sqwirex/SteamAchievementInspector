import sys
import re
import time
import csv
import threading
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set, Tuple

import requests
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

API_BASE = "https://api.steampowered.com"
HEADERS = {"User-Agent": "SteamAchievementInspector/3.2 (+https://github.com/yourname/SteamAchievementInspector)"}


def compact_elide(text: str, font_metrics: QtGui.QFontMetrics, width: int) -> str:
    if not text:
        return ""
    if width <= 0:
        return "..."
    if font_metrics.horizontalAdvance(text) <= width:
        return text
    ellipsis = "..."
    ellipsis_width = font_metrics.horizontalAdvance(ellipsis)
    if ellipsis_width >= width:
        return ellipsis
    trimmed = text.rstrip()
    while trimmed and font_metrics.horizontalAdvance(trimmed) + ellipsis_width > width:
        trimmed = trimmed[:-1].rstrip()
    return (trimmed or "") + ellipsis


def table_item_text_width(table: QtWidgets.QTableWidget, index: QtCore.QModelIndex) -> int:
    if not index.isValid():
        return 0
    rect = table.visualRect(index)
    col = index.column()
    if col == 0:
        return 0
    if col == 6:
        return max(0, rect.width() - 4)
    return max(0, rect.width() - 28)


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)


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
                "sort_label": "Sort",
                "n_label": "N (Δt) =",
                "filters_label": "Filters",
                "only_susp": "Suspicious (≤ N min)",
                "only_exact": "Identical timestamps",
                "reset": "Reset filters and sorting",
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
                "api_key": "API Ключ",
                "api_key_ph": "Steam Web API Key (32 hex)",
                "api_invalid": "Неверный Steam Web API ключ или нет доступа. "
                               "Проверьте ключ на https://steamcommunity.com/dev/apikey и попробуйте снова.",
                "language": "Язык",
                "load": "Загрузить",
                "stop": "Стоп",
                "game": "Игра",
                "sort_desc": "По времени: убыв.",
                "sort_asc": "По времени: возр.",
                "sort_label": "Сортировка",
                "n_label": "N (Δt) =",
                "filters_label": "Фильтры",
                "only_susp": "Подозрительные (≤ N мин)",
                "only_exact": "Одинаковые таймстампы",
                "reset": "Сброс фильтров и сортировки",
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

    def get_player_achievements_full(self, steamid64: str, appid: int) -> List[Dict]:
        url = f"{API_BASE}/ISteamUserStats/GetPlayerAchievements/v0001/"
        params = {"key": self.api_key, "steamid": steamid64, "appid": appid, "l": self.lang}
        data = self._get(url, params)
        ps = data.get("playerstats", {})
        if ps.get("success") is False:
            return []
        achievements = ps.get("achievements", []) or []
        return [
            {"apiname": item.get("apiname", ""), "unlocktime": int(item.get("unlocktime", 0) or 0)}
            for item in achievements
            if bool(item.get("achieved", 0))
        ]

    def get_schema_for_game(self, appid: int, lang: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        url = f"{API_BASE}/ISteamUserStats/GetSchemaForGame/v2/"
        params = {"key": self.api_key, "appid": appid, "l": lang or self.lang}
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
        self.initStyleOption(opt, index)
        State = getattr(QtWidgets.QStyle, "StateFlag", QtWidgets.QStyle)
        opt.state &= ~State.State_Selected
        opt.state &= ~State.State_MouseOver
        opt.state &= ~State.State_HasFocus

        if index.column() == 0:
            super().paint(painter, opt, index)
            return

        style = opt.widget.style() if opt.widget else QtWidgets.QApplication.style()
        opt.text = ""
        style.drawControl(QtWidgets.QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        text = str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or "")
        alignment_data = index.data(QtCore.Qt.ItemDataRole.TextAlignmentRole)
        if alignment_data is None:
            alignment = QtCore.Qt.AlignmentFlag.AlignCenter if index.column() == 6 else (QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        else:
            alignment = QtCore.Qt.AlignmentFlag(int(alignment_data))
            if not (alignment & (QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignVCenter)):
                alignment |= QtCore.Qt.AlignmentFlag.AlignVCenter

        if index.column() == 6:
            text_rect = opt.rect.adjusted(0, 0, 0, 0)
        else:
            text_rect = opt.rect.adjusted(14, 0, -14, 0)

        shown = compact_elide(text, opt.fontMetrics, max(0, text_rect.width()))

        painter.save()
        painter.setFont(opt.font)
        painter.setPen(QtGui.QColor("#dce8f3"))
        painter.drawText(text_rect, int(alignment), shown)
        painter.restore()


class CellPreviewPopup(QtWidgets.QWidget):
    def __init__(self):
        super().__init__(
            None,
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.NoDropShadowWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setObjectName("CellPreviewPopup")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.panel = QtWidgets.QFrame(self)
        self.panel.setObjectName("CellPreviewPanel")
        root.addWidget(self.panel)

        layout = QtWidgets.QVBoxLayout(self.panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(0)

        self.label = QtWidgets.QLabel()
        self.label.setObjectName("CellPreviewText")
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.label.setWordWrap(False)
        layout.addWidget(self.label)

        self.setStyleSheet(
            """
            QWidget#CellPreviewPopup {
                background: transparent;
            }
            QFrame#CellPreviewPanel {
                background: #111a25;
                border: 1px solid #31506d;
                border-radius: 12px;
            }
            QLabel#CellPreviewText {
                color: #eef6fc;
                background: transparent;
                font-size: 13px;
            }
            """
        )

    def show_for_text(self, text: str, anchor: QtCore.QPoint, max_width: int = 720):
        screen = QtGui.QGuiApplication.screenAt(anchor) or QtGui.QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1280, 720)
        margin = 8

        space_right = max(140, geo.right() - anchor.x() - margin)
        space_left = max(140, anchor.x() - geo.left() - margin)
        preferred_width = max(space_right, space_left)
        width_limit = max(140, min(max_width, geo.width() - margin * 2, preferred_width))

        self.label.setText(text)
        metrics = self.label.fontMetrics()
        desired_width = metrics.horizontalAdvance(text) + 8

        if desired_width > width_limit:
            self.label.setWordWrap(True)
            self.label.setFixedWidth(width_limit)
        else:
            self.label.setWordWrap(False)
            self.label.setFixedWidth(desired_width)

        self.adjustSize()

        if space_right >= self.width() or space_right >= space_left:
            pos_x = anchor.x()
            if pos_x + self.width() > geo.right() - margin:
                pos_x = max(geo.left() + margin, geo.right() - self.width() - margin)
        else:
            pos_x = anchor.x() - self.width() - 16
            if pos_x < geo.left() + margin:
                pos_x = geo.left() + margin

        pos_y = anchor.y()
        if pos_y + self.height() > geo.bottom() - margin:
            pos_y = anchor.y() - self.height() - 16
        if pos_y < geo.top() + margin:
            pos_y = geo.top() + margin
        if pos_y + self.height() > geo.bottom() - margin:
            pos_y = max(geo.top() + margin, geo.bottom() - self.height() - margin)

        self.move(int(pos_x), int(pos_y))
        self.show()
        self.raise_()


class CapsuleScrollBar(QtWidgets.QScrollBar):
    def __init__(self, orientation: QtCore.Qt.Orientation, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(orientation, parent)
        self._hover_handle = False
        self._reserved_start = 0
        self._dragging = False
        self._drag_offset = 0.0
        self.setMouseTracking(True)

        if orientation == QtCore.Qt.Orientation.Vertical:
            self.setFixedWidth(16)
        else:
            self.setFixedHeight(16)

        self.setStyleSheet("""
            QScrollBar {
                background: transparent;
                border: none;
            }
            QScrollBar::add-line,
            QScrollBar::sub-line,
            QScrollBar::add-page,
            QScrollBar::sub-page {
                width: 0px;
                height: 0px;
                background: transparent;
                border: none;
            }
        """)

    def set_reserved_start(self, value: int) -> None:
        value = max(0, int(value))
        if self._reserved_start != value:
            self._reserved_start = value
            self.update()

    def _is_vertical(self) -> bool:
        return self.orientation() == QtCore.Qt.Orientation.Vertical

    def _track_rect(self) -> QtCore.QRectF:
        rect = QtCore.QRectF(self.rect())

        if self._is_vertical():
            return rect.adjusted(4.6, self._reserved_start + 2, -3.4, -2)

        return rect.adjusted(2, 4.6, -2, -3.4)

    def _slider_rect(self) -> QtCore.QRectF:
        track = self._track_rect()
        vertical = self._is_vertical()

        track_len = max(1.0, track.height() if vertical else track.width())
        min_v = self.minimum()
        max_v = self.maximum()
        page = max(1, self.pageStep())
        span = max_v - min_v

        if span <= 0:
            ratio = 1.0
            pos_ratio = 0.0
        else:
            ratio = page / float(span + page)
            pos_ratio = (self.value() - min_v) / float(span)

        min_len = 40.0
        slider_len = max(min_len, track_len * ratio)
        slider_len = min(slider_len, track_len)
        slider_pos = (track_len - slider_len) * max(0.0, min(1.0, pos_ratio))

        if vertical:
            return QtCore.QRectF(track.x(), track.y() + slider_pos, track.width(), slider_len)
        return QtCore.QRectF(track.x() + slider_pos, track.y(), slider_len, track.height())

    def _event_axis_pos(self, event: QtGui.QMouseEvent) -> float:
        pos = event.position()
        return pos.y() if self._is_vertical() else pos.x()

    def _slider_axis_start(self) -> float:
        slider = self._slider_rect()
        return slider.y() if self._is_vertical() else slider.x()

    def _track_axis_start(self) -> float:
        track = self._track_rect()
        return track.y() if self._is_vertical() else track.x()

    def _track_axis_length(self) -> float:
        track = self._track_rect()
        return track.height() if self._is_vertical() else track.width()

    def _slider_axis_length(self) -> float:
        slider = self._slider_rect()
        return slider.height() if self._is_vertical() else slider.width()

    def _set_value_from_slider_axis_start(self, slider_start: float) -> None:
        min_v = self.minimum()
        max_v = self.maximum()
        span = max_v - min_v
        if span <= 0:
            return

        track_start = self._track_axis_start()
        movable_len = max(1.0, self._track_axis_length() - self._slider_axis_length())
        pos_ratio = (slider_start - track_start) / movable_len
        pos_ratio = max(0.0, min(1.0, pos_ratio))

        self.setValue(round(min_v + pos_ratio * span))

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        outline_pen = QtGui.QPen(QtGui.QColor("#2b3849"), 2)
        outline_pen.setCosmetic(True)
        painter.setPen(outline_pen)
        if self._is_vertical():
            painter.drawLine(0, 0, 0, self.height())
        else:
            painter.drawLine(0, 0, self.width(), 0)

        track = self._track_rect()
        if track.width() <= 0 or track.height() <= 0:
            return

        track_radius = min(track.width(), track.height()) / 2.0
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor("#101722"))
        painter.drawRoundedRect(track, track_radius, track_radius)

        if self.maximum() <= self.minimum():
            return

        handle = self._slider_rect()
        if handle.width() <= 0 or handle.height() <= 0:
            return

        handle_radius = min(handle.width(), handle.height()) / 2.0
        painter.setBrush(QtGui.QColor("#5f82aa") if (self._hover_handle or self._dragging) else QtGui.QColor("#4e7097"))
        painter.drawRoundedRect(handle, handle_radius, handle_radius)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        slider = self._slider_rect()
        axis_pos = self._event_axis_pos(event)

        if slider.contains(event.position()):
            self._dragging = True
            self._drag_offset = axis_pos - self._slider_axis_start()
            self.setSliderDown(True)
            self.grabMouse()
            event.accept()
            self.update()
            return

        if self._track_rect().contains(event.position()):
            self._dragging = True
            self._drag_offset = self._slider_axis_length() / 2.0
            self.setSliderDown(True)
            self.grabMouse()
            self._set_value_from_slider_axis_start(axis_pos - self._drag_offset)
            event.accept()
            self.update()
            return

        event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self._dragging:
            slider_start = self._event_axis_pos(event) - self._drag_offset
            self._set_value_from_slider_axis_start(slider_start)
            event.accept()
            self.update()
            return

        was_hover = self._hover_handle
        self._hover_handle = self._slider_rect().contains(event.position())
        if was_hover != self._hover_handle:
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if self._dragging and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setSliderDown(False)
            try:
                self.releaseMouse()
            except RuntimeError:
                pass
            event.accept()
            self.update()
            return

        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: QtCore.QEvent):
        if not self._dragging and self._hover_handle:
            self._hover_handle = False
            self.update()
        super().leaveEvent(event)


class QuietTable(QtWidgets.QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._preview_popup = CellPreviewPopup()
        self._last_preview_key: Optional[Tuple[int, int, str]] = None

    def _hide_preview(self):
        self._last_preview_key = None
        self._preview_popup.hide()

    def _item_needs_preview(self, index: QtCore.QModelIndex) -> bool:
        if not index.isValid() or index.column() not in (1, 2, 3, 4, 5):
            return False
        item = self.item(index.row(), index.column())
        if not item:
            return False
        text = item.text().strip()
        if not text:
            return False
        fm = QtGui.QFontMetrics(item.font())
        shown = compact_elide(text, fm, table_item_text_width(self, index))
        return shown != text

    def wheelEvent(self, e: QtGui.QWheelEvent) -> None:
        self._hide_preview()
        super().wheelEvent(e)
        QtCore.QTimer.singleShot(0, self._clear_current)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        index = self.indexAt(event.pos())
        if self._item_needs_preview(index):
            item = self.item(index.row(), index.column())
            text = item.text().strip()
            key = (index.row(), index.column(), text)
            if key != self._last_preview_key:
                self._last_preview_key = key
                anchor = event.globalPosition().toPoint() + QtCore.QPoint(8, -8)
                self._preview_popup.show_for_text(text, anchor)
        else:
            self._hide_preview()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if self._last_preview_key:
            pos = self.viewport().mapFromGlobal(QtGui.QCursor.pos())
            if self.viewport().rect().contains(pos):
                index = self.indexAt(pos)
                if index.isValid():
                    item = self.item(index.row(), index.column())
                    text = item.text().strip() if item else ""
                    if (index.row(), index.column(), text) == self._last_preview_key:
                        super().leaveEvent(event)
                        return
        self._hide_preview()
        super().leaveEvent(event)

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

            pa = api.get_player_achievements_full(self.steamid64, appid)
            achs: List[Achievement] = []
            if pa:
                if self.cancel_event.is_set():
                    return
                try:
                    schema = api.get_schema_for_game(appid, "en")
                except Exception:
                    schema = {}

                for a in pa:
                    apiname = a["apiname"]
                    meta = schema.get(apiname, {})
                    achs.append(
                        Achievement(
                            appid=appid,
                            game_name=gname,
                            apiname=apiname,
                            name=(meta.get("displayName") or apiname),
                            description=(meta.get("description") or ""),
                            icon_url=(meta.get("icon") or ""),
                            unlock_time=int(a["unlocktime"]),
                        )
                    )
                self.signals.partial.emit(achs)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.done.emit()


class ContextMenuRow(QtWidgets.QFrame):
    triggered = QtCore.pyqtSignal()

    def __init__(self, title: str, shortcut: str = "", enabled: bool = True, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ContextMenuRow")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor if enabled else QtCore.Qt.CursorShape.ArrowCursor)
        self.setEnabled(enabled)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setObjectName("ContextMenuRowTitle")
        self.shortcut_label = QtWidgets.QLabel(shortcut)
        self.shortcut_label.setObjectName("ContextMenuRowShortcut")
        self.shortcut_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        active_color = "#ffffff" if enabled else "#607286"
        self.title_label.setStyleSheet(f"color: {active_color}; background: transparent;")
        self.shortcut_label.setStyleSheet(f"color: {active_color}; background: transparent;")
        self.title_label.setEnabled(enabled)
        self.shortcut_label.setEnabled(enabled)

        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.shortcut_label)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.isEnabled() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.triggered.emit()
        super().mouseReleaseEvent(event)


class CustomTextContextMenu(QtWidgets.QWidget):
    def __init__(self, target: QtWidgets.QLineEdit):
        super().__init__(
            None,
            QtCore.Qt.WindowType.Popup
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.NoDropShadowWindowHint,
        )
        self.target = target
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("CustomTextContextMenu")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.panel = QtWidgets.QFrame(self)
        self.panel.setObjectName("CustomTextContextMenuPanel")
        root.addWidget(self.panel)

        self.layout_ = QtWidgets.QVBoxLayout(self.panel)
        self.layout_.setContentsMargins(8, 8, 8, 8)
        self.layout_.setSpacing(4)

        self.setStyleSheet(
            """
            QWidget#CustomTextContextMenu {
                background: transparent;
            }
            QFrame#CustomTextContextMenuPanel {
                background: #171e29;
                border: 1px solid #304255;
                border-radius: 14px;
            }
            QFrame#ContextMenuRow {
                background: transparent;
                border: none;
                border-radius: 10px;
            }
            QFrame#ContextMenuRow:hover {
                background: #223145;
            }
            QFrame#ContextMenuRow:disabled {
                background: transparent;
            }
            QLabel#ContextMenuRowTitle,
            QLabel#ContextMenuRowShortcut {
                color: #eef6fc;
                background: transparent;
            }
            QFrame#ContextMenuRow:disabled QLabel#ContextMenuRowTitle,
            QFrame#ContextMenuRow:disabled QLabel#ContextMenuRowShortcut {
                color: #607286;
            }
            QFrame#ContextMenuRow:hover QLabel#ContextMenuRowTitle,
            QFrame#ContextMenuRow:hover QLabel#ContextMenuRowShortcut {
                color: #ffffff;
            }
            """
        )

    def _add_action(self, title: str, shortcut: str, enabled: bool, callback: Callable[[], None]):
        row = ContextMenuRow(title, shortcut, enabled, self.panel)
        if enabled:
            row.triggered.connect(lambda cb=callback: (cb(), self.hide()))
        self.layout_.addWidget(row)

    def popup(self, global_pos: QtCore.QPoint):
        clipboard = QtWidgets.QApplication.clipboard().text()
        has_selection = bool(self.target.selectedText())
        read_only = self.target.isReadOnly()

        self._add_action("Undo", "Ctrl+Z", (not read_only) and self.target.isUndoAvailable(), self.target.undo)
        self._add_action("Redo", "Ctrl+Y", (not read_only) and self.target.isRedoAvailable(), self.target.redo)
        self._add_action("Cut", "Ctrl+X", (not read_only) and has_selection, self.target.cut)
        self._add_action("Copy", "Ctrl+C", has_selection, self.target.copy)
        self._add_action("Paste", "Ctrl+V", (not read_only) and bool(clipboard), self.target.paste)
        self._add_action("Delete", "Del", (not read_only) and has_selection, self.target.del_)
        self._add_action("Select All", "Ctrl+A", bool(self.target.text()), self.target.selectAll)

        self.adjustSize()
        pos = QtCore.QPoint(global_pos)
        screen = QtGui.QGuiApplication.screenAt(pos) or QtGui.QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            if pos.x() + self.width() > geo.right() - 8:
                pos.setX(max(geo.left() + 8, geo.right() - self.width() - 8))
            if pos.y() + self.height() > geo.bottom() - 8:
                pos.setY(max(geo.top() + 8, geo.bottom() - self.height() - 8))
        self.move(pos)
        self.show()
        self.raise_()


class ContextMenuLineEdit(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._context_menu_popup: Optional[CustomTextContextMenu] = None

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        self._context_menu_popup = CustomTextContextMenu(self)
        self._context_menu_popup.popup(event.globalPos())
        event.accept()


class StyledClearLineEdit(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._context_menu_popup: Optional[CustomTextContextMenu] = None
        self.setClearButtonEnabled(True)
        self.textChanged.connect(self._polish_clear_button)
        QtCore.QTimer.singleShot(0, self._polish_clear_button)

    @staticmethod
    def _clear_icon() -> QtGui.QIcon:
        size = 22
        pix = QtGui.QPixmap(size, size)
        pix.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor("#223145"))
        painter.drawRoundedRect(QtCore.QRectF(3, 3, 16, 16), 5, 5)
        pen = QtGui.QPen(QtGui.QColor("#ffd54f"), 2.0, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QtCore.QPointF(8, 8), QtCore.QPointF(14, 14))
        painter.drawLine(QtCore.QPointF(14, 8), QtCore.QPointF(8, 14))
        painter.end()
        return QtGui.QIcon(pix)

    def _polish_clear_button(self):
        button = self.findChild(QtWidgets.QToolButton)
        if not button:
            return
        button.setIcon(self._clear_icon())
        button.setIconSize(QtCore.QSize(22, 22))
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet("""
            QToolButton {
                border: 0px;
                background: transparent;
                padding: 0px;
                margin-right: 4px;
            }
            QToolButton:hover { background: transparent; }
        """)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        self._context_menu_popup = CustomTextContextMenu(self)
        self._context_menu_popup.popup(event.globalPos())
        event.accept()


class SmartSpinBox(QtWidgets.QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._context_menu_popup: Optional[CustomTextContextMenu] = None
        self.setLineEdit(ContextMenuLineEdit(self))
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.lineEdit().setCursorMoveStyle(QtCore.Qt.CursorMoveStyle.LogicalMoveStyle)
        self.lineEdit().setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.lineEdit().setTextMargins(0, 0, 18, 0)
        self._hover_arrow: Optional[str] = None
        self.setMouseTracking(True)

    def _arrow_rects(self) -> Tuple[QtCore.QRect, QtCore.QRect]:
        w = 14
        x = max(0, self.width() - w - 7)
        top = QtCore.QRect(x, 10, w, 9)
        bottom = QtCore.QRect(x, max(20, self.height() - 16), w, 9)
        return top, bottom

    def paintEvent(self, event: QtGui.QPaintEvent):
        super().paintEvent(event)
        up_rect, down_rect = self._arrow_rects()

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        def draw_arrow(rect: QtCore.QRect, direction: str):
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor("#f2c94c"))
            cx = rect.center().x()
            cy = rect.center().y()
            if direction == "up":
                points = [
                    QtCore.QPointF(cx, cy - 2.8),
                    QtCore.QPointF(cx - 3.6, cy + 2.8),
                    QtCore.QPointF(cx + 3.6, cy + 2.8),
                ]
            else:
                points = [
                    QtCore.QPointF(cx - 3.6, cy - 2.8),
                    QtCore.QPointF(cx + 3.6, cy - 2.8),
                    QtCore.QPointF(cx, cy + 2.8),
                ]
            painter.drawPolygon(QtGui.QPolygonF(points))

        draw_arrow(up_rect, "up")
        draw_arrow(down_rect, "down")

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        up_rect, down_rect = self._arrow_rects()
        pos = event.position().toPoint()
        old_hover = self._hover_arrow
        if up_rect.contains(pos):
            self._hover_arrow = "up"
        elif down_rect.contains(pos):
            self._hover_arrow = "down"
        else:
            self._hover_arrow = None
        if old_hover != self._hover_arrow:
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QtCore.QEvent):
        if self._hover_arrow is not None:
            self._hover_arrow = None
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            up_rect, down_rect = self._arrow_rects()
            pos = event.position().toPoint()
            if up_rect.contains(pos):
                self.stepUp()
                event.accept()
                return
            if down_rect.contains(pos):
                self.stepDown()
                event.accept()
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        self._context_menu_popup = CustomTextContextMenu(self.lineEdit())
        self._context_menu_popup.popup(event.globalPos())
        event.accept()


class ComboItemDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex):
        opt = QtWidgets.QStyleOptionViewItem(option)
        super().paint(painter, opt, index)
        if opt.state & QtWidgets.QStyle.StateFlag.State_Selected:
            painter.save()
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor("#ffd54f"))
            marker_area = QtCore.QRectF(opt.rect.right() - 26, opt.rect.top(), 20, opt.rect.height())
            side = 8.0
            r = QtCore.QRectF(
                marker_area.center().x() - side / 2.0,
                marker_area.center().y() - side / 2.0,
                side,
                side,
            )
            painter.drawRoundedRect(r, 2.0, 2.0)
            painter.restore()

class CustomComboPopup(QtWidgets.QWidget):
    itemClicked = QtCore.pyqtSignal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(
            parent,
            QtCore.Qt.WindowType.Popup
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("ComboPopup")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.panel = QtWidgets.QFrame(self)
        self.panel.setObjectName("ComboPopupPanel")
        root.addWidget(self.panel)

        panel_l = QtWidgets.QVBoxLayout(self.panel)
        panel_l.setContentsMargins(4, 5, 7, 7)
        panel_l.setSpacing(0)

        self.list = QtWidgets.QListWidget(self.panel)
        self.list.setObjectName("ComboPopupList")
        self.list.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.list.setMouseTracking(True)
        self.list.setUniformItemSizes(True)
        self.list.setItemDelegate(ComboItemDelegate(self.list))
        self.list.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.list.itemClicked.connect(self._on_item_clicked)
        panel_l.addWidget(self.list)

        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet(
            """
            QWidget#ComboPopup {
                background: transparent;
            }
            QFrame#ComboPopupPanel {
                background: #141c27;
                border: 1px solid #33485f;
                border-radius: 14px;
            }
            QListWidget#ComboPopupList {
                background: transparent;
                color: #edf5fb;
                border: none;
                outline: 0;
                padding: 0px;
            }
            QListWidget#ComboPopupList::item {
                min-height: 22px;
                padding: 10px 14px;
                margin: 2px 0px;
                border-radius: 10px;
                background: transparent;
            }
            QListWidget#ComboPopupList::item:hover {
                background: #223145;
                color: #ffffff;
            }
            QListWidget#ComboPopupList::item:selected {
                background: #118c98;
                color: #f8fdff;
            }
            QListWidget#ComboPopupList QScrollBar:vertical,
            QListWidget#ComboPopupList QScrollBar:horizontal {
                width: 0px;
                height: 0px;
                background: transparent;
                border: none;
            }
            QListWidget#ComboPopupList QScrollBar::handle:vertical,
            QListWidget#ComboPopupList QScrollBar::handle:horizontal,
            QListWidget#ComboPopupList QScrollBar::add-line:vertical,
            QListWidget#ComboPopupList QScrollBar::sub-line:vertical,
            QListWidget#ComboPopupList QScrollBar::add-page:vertical,
            QListWidget#ComboPopupList QScrollBar::sub-page:vertical,
            QListWidget#ComboPopupList QScrollBar::add-line:horizontal,
            QListWidget#ComboPopupList QScrollBar::sub-line:horizontal,
            QListWidget#ComboPopupList QScrollBar::add-page:horizontal,
            QListWidget#ComboPopupList QScrollBar::sub-page:horizontal {
                width: 0px;
                height: 0px;
                background: transparent;
                border: none;
            }
            """
        )

    def _on_item_clicked(self, item: QtWidgets.QListWidgetItem):
        row = self.list.row(item)
        self.itemClicked.emit(row)
        self.hide()


class CustomComboBox(QtWidgets.QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._popup = CustomComboPopup(self)
        self._popup.itemClicked.connect(self._apply_popup_index)

    def _apply_popup_index(self, row: int):
        if 0 <= row < self.count():
            self.setCurrentIndex(row)

    def hidePopup(self):
        self._popup.hide()
        super().hidePopup()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if self._popup.isVisible() and event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            row = self._popup.list.currentRow()
            if row >= 0:
                self._apply_popup_index(row)
                self.hidePopup()
                return
        super().keyPressEvent(event)

    def showPopup(self):
        self._popup.setFont(self.font())
        self._popup.list.setFont(self.font())
        self._popup.list.clear()
        for i in range(self.count()):
            item = QtWidgets.QListWidgetItem(self.itemText(i))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, self.itemData(i))
            self._popup.list.addItem(item)

        current = self.currentIndex()
        if 0 <= current < self._popup.list.count():
            self._popup.list.setCurrentRow(current)
            self._popup.list.scrollToItem(
                self._popup.list.item(current),
                QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter,
            )

        row_h = max(self._popup.list.sizeHintForRow(0), 42) if self._popup.list.count() else 42
        visible_rows = min(max(self._popup.list.count(), 1), 8)
        panel_margins = self._popup.panel.layout().contentsMargins()
        frame_w = panel_margins.left() + panel_margins.right()
        frame_h = panel_margins.top() + panel_margins.bottom()
        height = visible_rows * row_h + frame_h
        width = max(self.width(), self._popup.list.sizeHintForColumn(0) + 30 + frame_w, 170)

        self._popup.resize(width, height)
        self._popup.panel.setFixedSize(width, height)
        self._popup.list.setFixedSize(max(0, width - frame_w), max(0, height - frame_h))

        pos = self.mapToGlobal(QtCore.QPoint(0, self.height() + 6))
        screen = QtGui.QGuiApplication.screenAt(pos) or QtGui.QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            if pos.x() + width > geo.right():
                pos.setX(max(geo.left(), geo.right() - width))
            if pos.y() + height > geo.bottom():
                above = self.mapToGlobal(QtCore.QPoint(0, -height - 6)).y()
                pos.setY(max(geo.top(), above))

        self._popup.move(pos)
        self._popup.show()
        self._popup.raise_()
        self._popup.activateWindow()


class RoundedProgressBar(QtWidgets.QProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTextVisible(False)
        self.setFixedHeight(18)

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = rect.height() / 2.0

        painter.setPen(QtGui.QPen(QtGui.QColor("#2b3849"), 1))
        painter.setBrush(QtGui.QColor("#101722"))
        painter.drawRoundedRect(QtCore.QRectF(rect), radius, radius)

        rng = max(1, self.maximum() - self.minimum())
        ratio = (self.value() - self.minimum()) / rng
        ratio = max(0.0, min(1.0, ratio))
        fill_width = rect.width() * ratio
        if fill_width > 0:
            fill_rect = QtCore.QRectF(rect.x(), rect.y(), fill_width, rect.height())
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor("#f2c94c"))
            if fill_width >= rect.height():
                painter.drawRoundedRect(fill_rect, radius, radius)
            else:
                painter.drawRoundedRect(fill_rect, fill_width / 2.0, fill_width / 2.0)


class ThemedMessageDialog(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget], title: str, message: str, kind: str = "info"):
        super().__init__(parent)
        self._result = 0
        self._loop: Optional[QtCore.QEventLoop] = None
        self._title = title
        self._message = message
        self._kind = kind

        self.setObjectName("ThemedMessageOverlay")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        if parent is not None:
            parent.installEventFilter(self)
            self.setGeometry(parent.rect())
        else:
            self.resize(480, 260)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scrim = QtWidgets.QFrame()
        scrim.setObjectName("DialogScrim")
        outer.addWidget(scrim)

        scrim_layout = QtWidgets.QVBoxLayout(scrim)
        scrim_layout.setContentsMargins(18, 18, 18, 18)
        scrim_layout.setSpacing(0)
        scrim_layout.addStretch(1)

        center_row = QtWidgets.QHBoxLayout()
        center_row.addStretch(1)

        self.card = QtWidgets.QFrame()
        self.card.setObjectName("DialogFrame")
        self.card.setMinimumWidth(420)
        self.card.setMaximumWidth(460)
        center_row.addWidget(self.card)

        center_row.addStretch(1)
        scrim_layout.addLayout(center_row)
        scrim_layout.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self.card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QtWidgets.QFrame()
        title_bar.setObjectName("DialogTitleBar")
        title_bar.setFixedHeight(58)
        title_row = QtWidgets.QHBoxLayout(title_bar)
        title_row.setContentsMargins(18, 0, 12, 0)
        title_row.setSpacing(10)

        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setObjectName("DialogTitleLabel")
        title_row.addWidget(self.title_label, 1)

        close_btn = QtWidgets.QPushButton("×")
        close_btn.setObjectName("DialogCloseButton")
        close_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.reject)
        title_row.addWidget(close_btn, 0, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(title_bar)

        body = QtWidgets.QFrame()
        body.setObjectName("DialogBody")
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(22, 22, 22, 20)
        body_layout.setSpacing(18)

        content_row = QtWidgets.QHBoxLayout()
        content_row.setSpacing(16)

        icon_holder = QtWidgets.QLabel()
        icon_holder.setObjectName("DialogIconHolder")
        icon_holder.setFixedSize(60, 60)
        icon_holder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        sp_map = {
            "info": QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation,
            "warning": QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning,
            "error": QtWidgets.QStyle.StandardPixmap.SP_MessageBoxCritical,
        }
        bg_map = {
            "info": "#183854",
            "warning": "#4c3a12",
            "error": "#4b1e29",
        }
        pix = self.style().standardIcon(sp_map.get(kind, sp_map["info"])).pixmap(32, 32)
        icon_holder.setPixmap(pix)
        icon_holder.setStyleSheet(
            f"background: {bg_map.get(kind, '#183854')}; border: 1px solid #2b3849; border-radius: 30px;"
        )
        content_row.addWidget(icon_holder, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        self.message_label = QtWidgets.QLabel(message)
        self.message_label.setObjectName("DialogMessageLabel")
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.message_label.setMinimumWidth(240)
        content_row.addWidget(self.message_label, 1)
        body_layout.addLayout(content_row)

        buttons_row = QtWidgets.QHBoxLayout()
        buttons_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.setObjectName("DialogOkButton")
        ok_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        ok_btn.setFixedHeight(42)
        ok_btn.setMinimumWidth(104)
        ok_btn.clicked.connect(self.accept)
        buttons_row.addWidget(ok_btn)
        body_layout.addLayout(buttons_row)

        layout.addWidget(body)

        self.setStyleSheet("""
            QWidget#ThemedMessageOverlay {
                background: transparent;
            }
            QFrame#DialogScrim {
                background: rgba(4, 10, 18, 150);
            }
            QFrame#DialogFrame {
                background: #171e29;
                border: 1px solid #2b3849;
                border-radius: 16px;
            }
            QFrame#DialogTitleBar {
                background: #1d2836;
                border-bottom: 1px solid #2b3849;
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QFrame#DialogBody {
                background: #171e29;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }
            QLabel#DialogTitleLabel {
                color: #e8f1fb;
                font-size: 15px;
                font-weight: 800;
                background: transparent;
            }
            QLabel#DialogMessageLabel {
                color: #dbe7f3;
                font-size: 13px;
                background: transparent;
            }
            QPushButton#DialogCloseButton {
                background: transparent;
                color: #aebdcd;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: 700;
                padding: 0;
            }
            QPushButton#DialogCloseButton:hover {
                background: #212d3d;
                color: #f2c94c;
            }
            QPushButton#DialogCloseButton:pressed {
                background: #18212d;
            }
            QPushButton#DialogOkButton {
                border: 1px solid #334256;
                border-radius: 12px;
                padding: 6px 18px;
                font-weight: 800;
                color: #eef6fc;
                background: #202b3a;
            }
            QPushButton#DialogOkButton:hover { background: #263448; }
            QPushButton#DialogOkButton:pressed { background: #182231; }
        """)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        parent = self.parentWidget()
        if obj is parent and event.type() in (
            QtCore.QEvent.Type.Resize,
            QtCore.QEvent.Type.Move,
            QtCore.QEvent.Type.Show,
        ):
            self.setGeometry(parent.rect())
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if self.card.geometry().contains(event.position().toPoint()):
            super().mousePressEvent(event)
            return
        self.reject()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            self.accept()
            return
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def _finish(self, result: int):
        self._result = result
        parent = self.parentWidget()
        if parent is not None:
            parent.removeEventFilter(self)
        self.hide()
        if self._loop is not None and self._loop.isRunning():
            self._loop.quit()
        self.deleteLater()

    def accept(self):
        self._finish(1)

    def reject(self):
        self._finish(0)

    def exec(self) -> int:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._loop = QtCore.QEventLoop(self)
        self._loop.exec()
        return self._result

    @classmethod
    def information(cls, parent: Optional[QtWidgets.QWidget], title: str, message: str):
        return cls(parent, title, message, "info").exec()

    @classmethod
    def warning(cls, parent: Optional[QtWidgets.QWidget], title: str, message: str):
        return cls(parent, title, message, "warning").exec()

    @classmethod
    def critical(cls, parent: Optional[QtWidgets.QWidget], title: str, message: str):
        return cls(parent, title, message, "error").exec()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.i18n = I18n("en")

        self.setWindowTitle(self.i18n.t("app_title"))
        self.resize(1280, 760)
        self.setMinimumSize(760, 720)
        app_icon = QtGui.QIcon(resource_path("app.ico"))
        self.setWindowIcon(app_icon)
        QtWidgets.QApplication.instance().setWindowIcon(app_icon)

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
        self.settings = QtCore.QSettings("SqwireX", "SteamAchievementInspector")

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

        self._build_ui()
        self._load_session()
        self._retranslate_ui()
        QtCore.QTimer.singleShot(0, self._refresh_table_geometry)
        QtCore.QTimer.singleShot(50, self._refresh_table_geometry)

    def _build_ui(self):
        self._apply_modern_style()

        central = QtWidgets.QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)

        page = QtWidgets.QVBoxLayout(central)
        page.setContentsMargins(12, 12, 12, 12)
        page.setSpacing(10)

        hero = QtWidgets.QFrame()
        hero.setObjectName("Hero")
        hero_l = QtWidgets.QHBoxLayout(hero)
        hero_l.setContentsMargins(16, 12, 16, 12)
        hero_l.setSpacing(10)

        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(3)
        self.lbl_title = QtWidgets.QLabel("Steam Achievement Inspector")
        self.lbl_title.setObjectName("TitleLabel")
        self.lbl_subtitle = QtWidgets.QLabel("Analyze unlock timelines, detect suspicious clusters, export clean CSV reports.")
        self.lbl_subtitle.setObjectName("SubtitleLabel")
        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_subtitle)

        hero_l.addLayout(title_box, 1)

        page.addWidget(hero)

        controls_card = QtWidgets.QFrame()
        controls_card.setObjectName("Card")
        controls = QtWidgets.QVBoxLayout(controls_card)
        controls.setContentsMargins(12, 12, 12, 12)
        controls.setSpacing(10)

        top = QtWidgets.QGridLayout()
        top.setHorizontalSpacing(12)
        top.setVerticalSpacing(8)
        controls.addLayout(top)

        self.lbl_profile = QtWidgets.QLabel()
        self.lbl_profile.setObjectName("FieldLabel")
        self.edt_profile = StyledClearLineEdit()
        self.edt_profile.setMinimumWidth(0)
        self.edt_profile.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        self.lbl_api = QtWidgets.QLabel()
        self.lbl_api.setObjectName("FieldLabel")
        self.edt_key = StyledClearLineEdit()
        self.edt_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

        self.lbl_lang = QtWidgets.QLabel()
        self.lbl_lang.setObjectName("FieldLabel")
        self.cmb_lang = CustomComboBox()
        self.cmb_lang.addItem("English", userData="en")
        self.cmb_lang.addItem("Русский", userData="ru")
        self.cmb_lang.setCurrentIndex(0)
        self.cmb_lang.currentIndexChanged.connect(self.on_ui_lang_changed)

        self.btn_fetch = QtWidgets.QPushButton()
        self.btn_fetch.setObjectName("PrimaryButton")
        self.btn_fetch.clicked.connect(self.on_fetch)

        self.btn_stop = QtWidgets.QPushButton()
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.on_stop)

        self.btn_export = QtWidgets.QPushButton()
        self.btn_export.setObjectName("GhostButton")
        self.btn_export.clicked.connect(self.export_csv)

        top.addWidget(self.lbl_profile, 0, 0)
        top.addWidget(self.edt_profile, 0, 1, 1, 5)

        top.addWidget(self.lbl_api, 1, 0)
        top.addWidget(self.edt_key, 1, 1, 1, 3)
        top.addWidget(self.lbl_lang, 1, 4)
        top.addWidget(self.cmb_lang, 1, 5)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.btn_fetch)
        actions.addWidget(self.btn_stop)
        actions.addWidget(self.btn_export)
        actions.setStretch(0, 1)
        actions.setStretch(1, 1)
        actions.setStretch(2, 1)

        top.setColumnStretch(1, 2)
        top.setColumnStretch(2, 2)
        top.setColumnStretch(3, 2)
        top.setColumnStretch(5, 1)

        filters = QtWidgets.QGridLayout()
        filters.setHorizontalSpacing(12)
        filters.setVerticalSpacing(8)
        controls.addLayout(filters)

        self.lbl_game = QtWidgets.QLabel()
        self.lbl_game.setObjectName("FieldLabel")
        self.cmb_game = CustomComboBox()
        self.cmb_game.addItem("", userData=None)
        self.cmb_game.currentIndexChanged.connect(self.refresh_table)

        self.cmb_sort = CustomComboBox()
        self.cmb_sort.currentIndexChanged.connect(self.refresh_table)

        self.lbl_sorting = QtWidgets.QLabel()
        self.lbl_sorting.setObjectName("FieldLabel")

        self.lbl_n = QtWidgets.QLabel()
        self.lbl_n.setObjectName("FieldLabel")
        self.spin_n = SmartSpinBox()
        self.spin_n.setRange(1, 1440)
        self.spin_n.setValue(2)
        self.spin_n.setFixedWidth(98)
        self.spin_n.valueChanged.connect(self.refresh_table)
        self.lbl_n_unit = QtWidgets.QLabel()
        self.lbl_n_unit.setObjectName("FieldLabel")

        self.chk_only_susp = QtWidgets.QCheckBox()
        self.chk_only_susp.stateChanged.connect(self.refresh_table)

        self.chk_only_exact = QtWidgets.QCheckBox()
        self.chk_only_exact.stateChanged.connect(self.refresh_table)

        self.lbl_filters = QtWidgets.QLabel()
        self.lbl_filters.setObjectName("FieldLabel")

        self.btn_reset = QtWidgets.QPushButton()
        self.btn_reset.setObjectName("GhostButton")
        self.btn_reset.clicked.connect(self.reset_filters)

        filters.addWidget(self.lbl_game, 0, 0)
        filters.addWidget(self.cmb_game, 0, 1, 1, 5)

        sort_n_row = QtWidgets.QHBoxLayout()
        sort_n_row.setSpacing(10)
        sort_n_row.addWidget(self.cmb_sort, 1)
        sort_n_row.addWidget(self.lbl_n)
        sort_n_row.addWidget(self.spin_n)
        sort_n_row.addWidget(self.lbl_n_unit)
        filters.addWidget(self.lbl_sorting, 1, 0)
        filters.addLayout(sort_n_row, 1, 1, 1, 5)

        filter_flags = QtWidgets.QHBoxLayout()
        filter_flags.setSpacing(12)
        filter_flags.addWidget(self.chk_only_susp)
        filter_flags.addWidget(self.chk_only_exact)
        filter_flags.addStretch(1)
        filter_flags.addWidget(self.btn_reset)
        filters.addWidget(self.lbl_filters, 2, 0)
        filters.addLayout(filter_flags, 2, 1, 1, 5)

        filters.setColumnStretch(1, 2)
        filters.setColumnStretch(2, 2)
        filters.setColumnStretch(3, 2)
        filters.setColumnStretch(4, 2)
        filters.setColumnStretch(5, 2)

        controls.addLayout(actions)

        page.addWidget(controls_card)

        table_card = QtWidgets.QFrame()
        table_card.setObjectName("TableCard")
        table_l = QtWidgets.QVBoxLayout(table_card)
        table_l.setContentsMargins(1, 1, 1, 1)
        table_l.setSpacing(0)

        self.table = QuietTable(0, 7)
        self.table.setObjectName("AchievementTable")
        self.table_v_scroll = CapsuleScrollBar(QtCore.Qt.Orientation.Vertical, self.table)
        self.table_h_scroll = CapsuleScrollBar(QtCore.Qt.Orientation.Horizontal, self.table)
        self.table.setVerticalScrollBar(self.table_v_scroll)
        self.table.setHorizontalScrollBar(self.table_h_scroll)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setIconSize(QtCore.QSize(34, 34))
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        self.table.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.table.setCornerButtonEnabled(False)
        self.table.setItemDelegate(NoHighlightDelegate(self.table))
        self.table.viewport().installEventFilter(self)
        self.table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        hh = self.table.horizontalHeader()
        hh.setDefaultSectionSize(200)
        hh.setMinimumSectionSize(44)
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 70)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 220)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 260)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3, 380)
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(4, 170)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(5, 90)
        hh.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 46)

        table_l.addWidget(self.table, 1)
        self._apply_compact_table_columns()

        self.table_scroll_header = QtWidgets.QFrame(self.table)
        self.table_scroll_header.setObjectName("TableScrollHeader")
        self.table_scroll_header.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.table_scroll_header.hide()
        self.table.verticalScrollBar().rangeChanged.connect(lambda *_: (self._apply_compact_table_columns(), self._update_table_scroll_header()))
        self.table.horizontalHeader().geometriesChanged.connect(self._update_table_scroll_header)
        self.table.horizontalScrollBar().rangeChanged.connect(lambda *_: self._update_table_scroll_header())

        page.addWidget(table_card, 1)

        status_card = QtWidgets.QFrame()
        status_card.setObjectName("StatusCard")
        bottom = QtWidgets.QHBoxLayout(status_card)
        bottom.setContentsMargins(14, 10, 14, 10)
        bottom.setSpacing(12)

        self.progress = RoundedProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.lbl_status = QtWidgets.QLabel()
        self.lbl_status.setObjectName("StatusLabel")
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.lbl_status)
        page.addWidget(status_card)


    def _apply_modern_style(self):
        QtWidgets.QApplication.setStyle("Fusion")
        style = """
            QWidget#Root {
                background: #0f141d;
                color: #dbe7f3;
                font-family: "Segoe UI", "Inter", "Arial";
                font-size: 13px;
            }
            QFrame#Hero, QFrame#Card, QFrame#StatusCard, QFrame#TableCard {
                background: #171e29;
                border: 1px solid #273344;
                border-radius: 16px;
            }
            QFrame#Hero {
                background: #1d2836;
            }
            QFrame#TableCard {
                background: #1d2836;
                border: 1px solid #243244;
                border-radius: 0px;
            }
            QLabel#TitleLabel {
                color: #f6f9fc;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#SubtitleLabel, QLabel#StatusLabel {
                color: #98aabd;
            }
            QLabel#FieldLabel {
                color: #aebdcd;
                font-weight: 700;
            }
            QLineEdit, QComboBox, QSpinBox {
                background: #101722;
                color: #edf5fb;
                border: 1px solid #2b3849;
                border-radius: 12px;
                padding: 7px 10px;
                min-height: 20px;
                selection-background-color: #c99718;
                selection-color: #0f141d;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #f2c94c;
                background: #121c28;
            }
            QComboBox {
                padding-right: 30px;
                border-radius: 12px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border: 0px;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                width: 8px;
                height: 8px;
                margin-right: 0px;
                background: #f2c94c;
                border-radius: 2px;
            }
            QComboBox:on {
                border: 1px solid #f2c94c;
                background: #121c28;
            }
            QComboBox QAbstractItemView {
                background: #141c27;
                color: #edf5fb;
                border: 1px solid #36465c;
                border-radius: 12px;
                outline: 0;
                padding: 6px;
                margin: 0px;
                selection-background-color: #118c98;
                selection-color: #f8fdff;
            }
            QComboBox QAbstractItemView::item {
                min-height: 30px;
                padding: 8px 10px;
                border-radius: 8px;
                margin: 2px 0px;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #118c98;
                color: #f8fdff;
            }
            QComboBox QListView {
                background: #141c27;
                border: 0px;
                border-radius: 12px;
                padding: 6px;
            }
            QComboBox QListView::item {
                background: transparent;
            }
            QSpinBox {
                padding-right: 24px;
            }
            QPushButton {
                border: 1px solid #334256;
                border-radius: 12px;
                padding: 8px 12px;
                font-weight: 800;
                color: #eef6fc;
                background: #202b3a;
            }
            QPushButton:hover { background: #263448; }
            QPushButton:pressed { background: #182231; }
            QPushButton:disabled {
                color: #6f7f8f;
                background: #151c26;
                border-color: #242e3d;
            }
            QPushButton#PrimaryButton {
                background: #f2c94c;
                border-color: #ffd666;
                color: #2d2106;
            }
            QPushButton#PrimaryButton:hover { background: #f6d565; }
            QPushButton#PrimaryButton:pressed { background: #ddb53d; }
            QPushButton#DangerButton {
                background: #3a2028;
                border-color: #713444;
                color: #ffd9df;
            }
            QPushButton#DangerButton:hover { background: #542733; }
            QPushButton#GhostButton {
                background: transparent;
                color: #c4d1de;
                border-color: #3a4b60;
            }
            QPushButton#GhostButton:hover {
                background: #18212d;
                color: #ffd34d;
                border-color: #50647d;
            }
            QCheckBox {
                color: #dbe7f3;
                spacing: 8px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 6px;
                border: 1px solid #3a4a5f;
                background: #101722;
            }
            QCheckBox::indicator:checked {
                background: #f2c94c;
                border: 1px solid #ffd666;
            }
            QTableWidget#AchievementTable {
                background: #111822;
                alternate-background-color: #141d29;
                color: #dce8f3;
                border: 0px;
                border-bottom: 0px;
                border-radius: 0px;
                gridline-color: #263344;
            }
            QTableWidget#AchievementTable::item {
                padding: 7px;
                border-bottom: 1px solid #202b3a;
            }
            QTableWidget#AchievementTable::item:selected {
                background: transparent;
                color: #dce8f3;
            }
            QHeaderView::section {
                background: #1d2836;
                color: #a7bad0;
                border: 0px;
                border-right: 1px solid #2b3849;
                border-bottom: 1px solid #2b3849;
                padding: 7px;
                font-weight: 800;
            }
            QHeaderView::section:first {
                border-top-left-radius: 0px;
            }
            QHeaderView::section:last {
                border-top-right-radius: 0px;
                border-right: 0px;
            }
            QTableCornerButton::section {
                background: #1d2836;
                border: 0px;
                border-right: 1px solid #2b3849;
                border-bottom: 1px solid #2b3849;
                border-top-left-radius: 0px;
            }
            QAbstractScrollArea::corner {
                background: #101722;
                border-top: 1px solid #2b3849;
                border-left: 1px solid #2b3849;
            }
            QFrame#TableScrollHeader {
                background: #1d2836;
                border-left: 2px solid #2b3849;
                border-right: 0px;
                border-bottom: 1px solid #2b3849;
                border-top: 0px;
                margin: 0px;
                padding: 0px;
            }
            QTableWidget#AchievementTable QScrollBar:vertical {
                background: transparent;
                border: none;
                width: 16px;
                margin: 0px;
            }
            QTableWidget#AchievementTable QScrollBar:horizontal {
                background: transparent;
                border: none;
                height: 16px;
                margin: 0px;
            }
            QTableWidget#AchievementTable QScrollBar::handle:vertical,
            QTableWidget#AchievementTable QScrollBar::handle:horizontal,
            QTableWidget#AchievementTable QScrollBar::add-line:vertical,
            QTableWidget#AchievementTable QScrollBar::sub-line:vertical,
            QTableWidget#AchievementTable QScrollBar::add-line:horizontal,
            QTableWidget#AchievementTable QScrollBar::sub-line:horizontal,
            QTableWidget#AchievementTable QScrollBar::add-page:vertical,
            QTableWidget#AchievementTable QScrollBar::sub-page:vertical,
            QTableWidget#AchievementTable QScrollBar::add-page:horizontal,
            QTableWidget#AchievementTable QScrollBar::sub-page:horizontal {
                background: transparent;
                border: none;
            }
        """
        self.setStyleSheet(style)
    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self.table.viewport():
            if event.type() in (
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QEvent.Type.MouseButtonRelease,
                QtCore.QEvent.Type.MouseButtonDblClick,
            ):
                return True
        return super().eventFilter(obj, event)

    def _refresh_table_geometry(self):
        self._apply_compact_table_columns()
        self._update_table_scroll_header()
        self.table.viewport().update()
        self.table.horizontalHeader().viewport().update()

    def showEvent(self, event: QtGui.QShowEvent):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._refresh_table_geometry)
        QtCore.QTimer.singleShot(50, self._refresh_table_geometry)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._refresh_table_geometry)

    def _apply_compact_table_columns(self):
        if not hasattr(self, "table"):
            return

        for col in range(7):
            self.table.setColumnHidden(col, False)

        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)

        base_widths = [70, 220, 260, 380, 170, 90, 46]
        for col, width in enumerate(base_widths):
            if col in (0, 6):
                hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Fixed)
            elif col == 3:
                pass
            else:
                hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, width)

        viewport_width = self.table.viewport().width()
        total_base = sum(base_widths)

        if viewport_width >= total_base:
            hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        else:
            hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(3, base_widths[3])

    def _update_table_scroll_header(self):
        if not hasattr(self, "table_scroll_header"):
            return

        sb = self.table.verticalScrollBar()
        header = self.table.horizontalHeader()
        if header.width() <= 0 or self.table.viewport().width() <= 0:
            self.table_scroll_header.hide()
            return
        if not sb.isVisible() or sb.maximum() <= 0:
            if hasattr(sb, "set_reserved_start"):
                sb.set_reserved_start(0)
            self.table_scroll_header.hide()
            return

        sb_geo = sb.geometry()
        hdr_geo = header.geometry()

        if hasattr(sb, "set_reserved_start"):
            sb.set_reserved_start(hdr_geo.height() + 1)
        x = max(0, self.table.width() - sb_geo.width() - 1)
        y = hdr_geo.y()
        w = sb_geo.width() + 1
        h = hdr_geo.height()
        self.table_scroll_header.setGeometry(x, y, w, h)
        self.table_scroll_header.show()
        self.table_scroll_header.raise_()

    def _retranslate_ui(self):
        t = self.i18n.t
        self.setWindowTitle(t("app_title"))
        self.lbl_title.setText(t("app_title"))
        self.lbl_subtitle.setText("Analyze unlock timelines, detect suspicious clusters, export clean CSV reports." if self.i18n.lang == "en" else "Анализ таймлайна достижений, поиск подозрительных кластеров и экспорт в CSV.")
        self.lbl_profile.setText(t("profile") + ":")
        self.edt_profile.setPlaceholderText(t("profile_ph"))
        self.lbl_api.setText(t("api_key") + ":")
        self.edt_key.setPlaceholderText(t("api_key_ph"))
        self.lbl_lang.setText(t("language") + ":")
        self.btn_fetch.setText(t("load"))
        self.btn_stop.setText(t("stop"))
        self.btn_export.setText(t("export_csv").replace("…", ""))
        self.lbl_game.setText(t("game") + ":")
        self.cmb_sort.blockSignals(True)
        self.cmb_sort.clear()
        self.cmb_sort.addItems([t("sort_desc"), t("sort_asc")])
        self.cmb_sort.blockSignals(False)
        self.lbl_sorting.setText(t("sort_label") + ":")
        self.lbl_n.setText(t("n_label"))
        self.lbl_n_unit.setText("min" if self.i18n.lang == "en" else "мин")
        self.lbl_filters.setText(t("filters_label") + ":")
        self.chk_only_susp.setText(t("only_susp"))
        self.chk_only_exact.setText(t("only_exact"))
        self.btn_reset.setText(t("reset"))
        self.table.setHorizontalHeaderLabels(
            [t("hdr_icon"), t("hdr_game"), t("hdr_ach"), t("hdr_desc"), t("hdr_time"), t("hdr_delta"), t("hdr_flag")]
        )
        self.lbl_status.setText(t("ready"))
        self.cmb_game.blockSignals(True)
        if self.cmb_game.count() == 0:
            self.cmb_game.addItem(t("all_games"), userData=None)
        else:
            self.cmb_game.setItemText(0, t("all_games"))
        self.cmb_game.blockSignals(False)

    def _load_session(self):
        api_key = self.settings.value("api_key", "", type=str) or ""
        profile_url = self.settings.value("profile_url", "", type=str) or ""
        lang = self.settings.value("language", "en", type=str) or "en"

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

    def _save_session(self):
        self.settings.setValue("api_key", self.edt_key.text().strip())
        self.settings.setValue("profile_url", self.edt_profile.text().strip())
        self.settings.setValue("language", self.cmb_lang.currentData() or "en")
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

    def on_fetch(self):
        url = self.edt_profile.text().strip()
        key = self.edt_key.text().strip()
        lang = "en"

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
        self.btn_fetch.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress.setValue(0)
        self.achievements.clear()
        self.loaded_games = 0
        self.games_index.clear()
        self._game_queue.clear()
        self._active_workers = 0
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
            worker.signals.error.connect(lambda _msg, w=worker: self._safe_remove_worker(w))
            worker.signals.done.connect(lambda w=worker: (self._safe_remove_worker(w), self._on_game_done()))

            self._active_workers += 1
            self.threadpool.start(worker)

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
        ThemedMessageDialog.critical(self, self.i18n.t("error"), message)

    def _base_items(self) -> List[Achievement]:
        items = self.achievements[:]
        appid = self.cmb_game.currentData()
        if appid:
            items = [a for a in items if a.appid == appid]
        return items

    def _achievement_display_name(self, a: Achievement) -> str:
        return a.name or a.apiname

    def _achievement_display_description(self, a: Achievement) -> str:
        return a.description or ""

    def _sort_items_for_view(self, items: List[Achievement]) -> List[Achievement]:
        asc = (self.cmb_sort.currentIndex() == 1)
        return sorted(items, key=lambda a: (a.unlock_time or 0, a.game_name, self._achievement_display_name(a)), reverse=not asc)

    def _filtered_sorted(self) -> List[Achievement]:
        items = self._base_items()
        ordered = self._sort_items_for_view(items)

        n_minutes = self.spin_n.value()
        exact_on = self.chk_only_exact.isChecked()
        susp_on  = self.chk_only_susp.isChecked()

        if exact_on and susp_on:
            within = self._filter_within_n(ordered, n_minutes)
            exact  = self._filter_exact_timestamp(ordered)
            want_ids = {id(x) for x in within} | {id(x) for x in exact}
            return [x for x in ordered if id(x) in want_ids]

        if exact_on:
            return self._filter_exact_timestamp(ordered)

        if susp_on:
            return self._filter_within_n(ordered, n_minutes)

        return ordered

    def _delta_map_ascending(self, items: List[Achievement]) -> Dict[int, Optional[int]]:
        chronological = sorted(items, key=lambda a: (a.unlock_time or 0, a.game_name, a.name))
        deltas: Dict[int, Optional[int]] = {}
        prev_ts: Optional[int] = None
        for a in chronological:
            if prev_ts is None or not a.unlock_time:
                deltas[id(a)] = None
            else:
                deltas[id(a)] = abs(a.unlock_time - prev_ts)
            if a.unlock_time:
                prev_ts = a.unlock_time
        return deltas

    def _filter_within_n(self, items: List[Achievement], n_minutes: int) -> List[Achievement]:
        if n_minutes <= 0 or len(items) < 2:
            return []
        n_sec = n_minutes * 60
        marked_ids = set()
        chronological = sorted(items, key=lambda a: (a.unlock_time or 0, a.game_name, a.name))
        for i in range(len(chronological) - 1):
            a, b = chronological[i], chronological[i + 1]
            if not (a.unlock_time and b.unlock_time):
                continue
            diff = abs(b.unlock_time - a.unlock_time)
            if 0 < diff <= n_sec:
                marked_ids.add(id(a))
                marked_ids.add(id(b))
        return [a for a in items if id(a) in marked_ids]

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

        source_items = self._base_items()
        delta_by_id = self._delta_map_ascending(source_items)
        exact_count: Dict[int, int] = {}
        for a in source_items:
            if a.unlock_time:
                exact_count[a.unlock_time] = exact_count.get(a.unlock_time, 0) + 1

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
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(self._achievement_display_name(a)))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(self._achievement_display_description(a)))

            dt = a.unlock_dt()
            ts_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else t.t("dash")
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(ts_str))

            d = delta_by_id.get(id(a))
            if d is None or not a.unlock_time:
                delta_str = t.t("dash"); delta_ok = False
            else:
                mins = d // 60; secs = d % 60
                delta_str = (t.fmt("mins_secs_fmt", m=mins, s=secs) if mins > 0
                             else t.fmt("secs_fmt", s=secs))
                delta_ok = d <= max(1, n_sec_threshold)
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
        self._update_table_scroll_header()

    def reset_filters(self):
        self.cmb_game.setCurrentIndex(0)
        self.cmb_sort.setCurrentIndex(0)
        self.spin_n.setValue(2)
        self.chk_only_susp.setChecked(False)
        self.chk_only_exact.setChecked(False)
        self.refresh_table()

    def _clear_input_selection_after_dialog(self):
        for line_edit in self.findChildren(QtWidgets.QLineEdit):
            line_edit.deselect()
            line_edit.clearFocus()
        self.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def _threshold_label(self) -> str:
        if self.chk_only_exact.isChecked():
            return self.i18n.t("thr_exact")
        n = self.spin_n.value()
        return self.i18n.fmt("thr_leq", n=n)

    def _csv_text(self, value: str) -> str:
        text = str(value or "")
        replacements = {
            "≤": "<=",
            "Δ": "Delta",
            "⚠": "!",
            "—": "-",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def _csv_delta_text(self, value: str) -> str:
        text = self._csv_text(value)
        if self.i18n.lang == "en":
            text = text.replace("м", "m").replace("с", "s")
        else:
            text = text.replace("m", "м").replace("s", "с")

        return text

    def _csv_default_filename(self) -> str:
        return "achievements.csv" if self.i18n.lang == "en" else "достижения.csv"

    def export_csv(self):
        t = self.i18n.t
        if self.table.rowCount() == 0:
            ThemedMessageDialog.information(self, t("info"), t("export_none"))
            self._clear_input_selection_after_dialog()
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("save_csv"),
                                                        self._csv_default_filename(), "CSV (*.csv)")
        if not path:
            return

        exported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game_filter = self.cmb_game.currentText() or t("all_games")
        sort_label = self.cmb_sort.currentText()
        threshold_text = self._threshold_label()
        only_susp = "on" if self.chk_only_susp.isChecked() else "off"
        only_exact = "on" if self.chk_only_exact.isChecked() else "off"

        def write_csv(to_path: str):
            with open(to_path, "w", newline="", encoding="cp1251", errors="replace") as f:
                if self.i18n.lang == "ru":
                    export_title = "Экспорт Steam Achievement Inspector"
                    exported_label = "Экспортировано"
                    profile_label = "Профиль"
                    ui_language_label = "Язык интерфейса"
                    game_filter_label = "Фильтр игр"
                    sort_label_name = "Сортировка"
                    threshold_label = "Порог"
                    only_suspicious_label = "Фильтр подозрительных"
                    only_exact_label = "Фильтр одинаковых таймстампов"
                else:
                    export_title = "Steam Achievement Inspector export"
                    exported_label = "Exported"
                    profile_label = "Profile"
                    ui_language_label = "UI language"
                    game_filter_label = "Game filter"
                    sort_label_name = "Sort"
                    threshold_label = "Threshold"
                    only_suspicious_label = "Only suspicious filter"
                    only_exact_label = "Only exact filter"

                f.write("sep=;\n")
                f.write(f"# {self._csv_text(export_title)}\n")
                f.write(f"# {self._csv_text(exported_label)}: {self._csv_text(exported_at)}\n")
                f.write(f"# {self._csv_text(profile_label)}: {self._csv_text(self.current_profile_url)}\n")
                f.write(f"# {self._csv_text(ui_language_label)}: {self._csv_text(self.i18n.lang)}\n")
                f.write(f"# {self._csv_text(game_filter_label)}: {self._csv_text(game_filter)}\n")
                f.write(f"# {self._csv_text(sort_label_name)}: {self._csv_text(sort_label)}\n")
                f.write(f"# {self._csv_text(threshold_label)}: {self._csv_text(threshold_text)}\n")
                f.write(f"# {self._csv_text(only_suspicious_label)}: {self._csv_text(only_susp)}\n")
                f.write(f"# {self._csv_text(only_exact_label)}: {self._csv_text(only_exact)}\n")

                w = csv.writer(f, delimiter=";")
                w.writerow([
                    self._csv_text(t("hdr_game")),
                    self._csv_text(t("hdr_ach")),
                    self._csv_text(t("hdr_desc")),
                    self._csv_text(t("hdr_time")),
                    "Delta t",
                    "Suspicious",
                ])
                for r in range(self.table.rowCount()):
                    def cell_text(c):
                        it = self.table.item(r, c)
                        return it.text() if it else ""

                    w.writerow([
                        self._csv_text(cell_text(1)),
                        self._csv_text(cell_text(2)),
                        self._csv_text(cell_text(3)),
                        self._csv_text(cell_text(4)),
                        self._csv_delta_text(cell_text(5)),
                        (self._csv_text(t("susp_yes")) if cell_text(6) else ""),
                    ])

        try:
            write_csv(path)
        except PermissionError:
            base, ext = os.path.splitext(path)
            alt = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext or '.csv'}"
            ThemedMessageDialog.warning(
                self, self.i18n.t("error"),
                "Can't write the file (permission denied). Close it in Excel or choose another path."
            )
            new_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("save_csv"), alt, "CSV (*.csv)")
            if new_path:
                write_csv(new_path)
            else:
                return

        ThemedMessageDialog.information(self, t("info"), t("export_done"))
        self._clear_input_selection_after_dialog()


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()