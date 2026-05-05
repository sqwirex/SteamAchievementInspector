import csv
import os
import threading
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Set

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from sai.i18n import I18n
from sai.models import Achievement
from sai.paths import resource_path
from sai.steam_api import SteamAPI
from sai.workers import GameFetchWorker, ListGamesWorker
from sai.ui.delegates import NoHighlightDelegate
from sai.ui.popups import ThemedMessageDialog
from sai.ui.scrollbars import CapsuleScrollBar
from sai.ui.widgets import CustomComboBox, QuietTable, RoundedProgressBar, SmartSpinBox, StyledClearLineEdit


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
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
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
    def _is_field_or_field_child(self, widget: Optional[QtWidgets.QWidget]) -> bool:
        while widget is not None:
            if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QComboBox, QtWidgets.QSpinBox)):
                return True
            widget = widget.parentWidget()
        return False

    def _clear_control_focus_on_background_click(self, obj: QtCore.QObject) -> None:
        if not isinstance(obj, QtWidgets.QWidget):
            return
        if obj.window() is not self:
            return
        if self._is_field_or_field_child(obj):
            return

        focused = QtWidgets.QApplication.focusWidget()
        if focused and focused.window() is self:
            focused.clearFocus()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            self._clear_control_focus_on_background_click(obj)

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