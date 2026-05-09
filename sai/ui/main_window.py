import csv
import os
import threading
from contextlib import suppress
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Optional, Set

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from sai.core.i18n import I18n
from sai.storage.cache import cache_size_bytes, clear_cache, cleanup_cache, read_icon_bytes, read_user_achievements, write_icon_bytes, write_user_achievements
from sai.core.models import Achievement
from sai.core.paths import app_exports_dir, resource_path
from sai.services.steam_api import SteamAPI
from sai.services.workers import GameFetchWorker, ListGamesWorker
from sai.ui.delegates import NoHighlightDelegate, OffsetHeaderView
from sai.ui.popups import ThemedMessageDialog
from sai.ui.scrollbars import CapsuleScrollBar
from sai.ui.widgets import CustomComboBox, QuietTable, RoundedProgressBar, SmartSpinBox, StyledClearLineEdit
from sai.ui.table_model import AchievementTableModel


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.i18n = I18n("en")

        self.setWindowTitle(self.i18n.t("app_title"))
        self.resize(1280, 760)
        self.setMinimumSize(760, 720)
        app_icon = QtGui.QIcon(resource_path("assets/app.ico"))
        self.setWindowIcon(app_icon)
        QtWidgets.QApplication.instance().setWindowIcon(app_icon)

        self.achievements: List[Achievement] = []
        self.games_index: Dict[int, str] = {}
        self.total_games: int = 0
        self.loaded_games: int = 0
        self.cancel_event = threading.Event()
        self._stopped_during_game_list_loading = False
        self._loading_game_list = False
        self._export_blocked_until_ready = False

        self._workers: List[QtCore.QRunnable] = []

        cpu = os.cpu_count() or 2
        self.max_workers: int = self._auto_worker_limit(cpu)
        self._game_queue: deque[Dict] = deque()
        self._active_workers: int = 0
        self.current_api_key = ""
        self.current_steamid = ""
        self.current_profile_url = ""
        self.settings = QtCore.QSettings("SqwireX", "SteamAchievementInspector")
        self.performance_mode: str = "auto"
        self.icons_enabled: bool = True
        self._status_key: str = "shown"
        self._status_kwargs: Dict[str, int] = {"n": 0}

        self.threadpool = QtCore.QThreadPool.globalInstance()
        self.threadpool.setMaxThreadCount(self.max_workers + 2)

        self.icon_cache: Dict[str, QtGui.QIcon] = {}
        self.icon_downloading: Set[str] = set()
        self.icon_replies: Dict[str, QNetworkReply] = {}
        self.net = QNetworkAccessManager(self)
        self.net.finished.connect(self._on_icon_loaded)
        self.max_icon_downloads: int = min(6, max(3, self.max_workers))
        self._pending_icon_urls: Deque[str] = deque()
        self._pending_icon_url_set: Set[str] = set()
        self._icon_rows: Dict[str, List[int]] = {}
        self._achievement_keys: Set[tuple] = set()
        self._achievement_loose_keys: Set[tuple] = set()
        self._analysis_cache_signature: Optional[tuple] = None
        self._analysis_cache_deltas: Dict[int, Optional[int]] = {}
        self._analysis_cache_exact_count: Dict[int, int] = {}

        self.visible_icon_timer = QtCore.QTimer(self)
        self.visible_icon_timer.setSingleShot(True)
        self.visible_icon_timer.setInterval(80)
        self.visible_icon_timer.timeout.connect(self._queue_visible_icons)

        self.cache_size_timer = QtCore.QTimer(self)
        self.cache_size_timer.setInterval(1500)
        self.cache_size_timer.timeout.connect(self._update_cache_button_text)
        self._last_cache_size_bytes: Optional[int] = None

        self.refresh_timer = QtCore.QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(150)
        self.refresh_timer.timeout.connect(lambda: self.refresh_table(update_status=False))

        self._menu_collapsed = False
        self._menu_animating = False
        self._toggle_button_pressed = False
        self._menu_animation_group: Optional[QtCore.QParallelAnimationGroup] = None

        cleanup_cache()

        self._build_ui()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._load_session()
        self._retranslate_ui()
        self._update_cache_button_text(force=True)
        self.cache_size_timer.start()
        QtCore.QTimer.singleShot(0, self._refresh_table_geometry)
        QtCore.QTimer.singleShot(50, self._refresh_table_geometry)


    @staticmethod
    def _auto_worker_limit(cpu_count: int) -> int:
        cpu = max(1, int(cpu_count or 1))
        if cpu <= 2:
            return 2
        if cpu <= 4:
            return 3
        if cpu <= 8:
            return 4
        if cpu <= 12:
            return 6
        return 8

    def _limits_for_performance_mode(self, mode: Optional[str] = None) -> tuple[int, int]:
        cpu = max(1, int(os.cpu_count() or 1))
        mode = mode or self.performance_mode
        if mode == "eco":
            return 2, 2
        if mode == "fast":
            workers = min(12, max(6, cpu))
            icons = min(8, max(4, cpu // 2))
            return workers, icons
        workers = self._auto_worker_limit(cpu)
        icons = min(6, max(3, workers))
        return workers, icons

    def _apply_performance_limits(self) -> None:
        self.max_workers, self.max_icon_downloads = self._limits_for_performance_mode()
        if hasattr(self, "threadpool"):
            self.threadpool.setMaxThreadCount(self.max_workers + max(2, self.max_icon_downloads // 2))

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
        self.controls_card = controls_card
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
        self.edt_key.installEventFilter(self)

        self.lbl_lang = QtWidgets.QLabel()
        self.lbl_lang.setObjectName("FieldLabel")
        self.cmb_lang = CustomComboBox()
        self.cmb_lang.setMinimumWidth(105)
        self.cmb_lang.setMaximumWidth(16777215)
        self.cmb_lang.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        for lang_code, lang_name in I18n.LANGUAGES.items():
            self.cmb_lang.addItem(lang_name, userData=lang_code)
        self.cmb_lang.setCurrentIndex(0)
        self.cmb_lang.currentIndexChanged.connect(self.on_ui_lang_changed)

        self.lbl_performance = QtWidgets.QLabel()
        self.lbl_performance.setObjectName("FieldLabel")
        self.cmb_performance = CustomComboBox()
        self.cmb_performance.setMinimumWidth(92)
        self.cmb_performance.setMaximumWidth(16777215)
        self.cmb_performance.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.cmb_performance.addItem("Auto", userData="auto")
        self.cmb_performance.addItem("Balanced", userData="eco")
        self.cmb_performance.addItem("Fast", userData="fast")
        self.cmb_performance.currentIndexChanged.connect(self.on_performance_mode_changed)

        self.lbl_icons = QtWidgets.QLabel()
        self.lbl_icons.setObjectName("FieldLabel")
        self.cmb_icons = CustomComboBox()
        self.cmb_icons.setMinimumWidth(105)
        self.cmb_icons.setMaximumWidth(16777215)
        self.cmb_icons.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.cmb_icons.addItem("Load icons", userData=True)
        self.cmb_icons.addItem("Do not load", userData=False)
        self.cmb_icons.setCurrentIndex(0)
        self.cmb_icons.currentIndexChanged.connect(self.on_icons_mode_changed)

        self.btn_fetch = QtWidgets.QPushButton()
        self.btn_fetch.setObjectName("PrimaryButton")
        self.btn_fetch.clicked.connect(self.on_fetch)

        self.btn_stop = QtWidgets.QPushButton()
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.clicked.connect(self.on_stop)

        self.btn_export = QtWidgets.QPushButton()
        self.btn_export.setObjectName("ExportButton")
        self.btn_export.clicked.connect(self.export_csv)

        self.btn_clear_cache = QtWidgets.QPushButton()
        self.btn_clear_cache.setObjectName("GhostButton")
        self.btn_clear_cache.setMinimumWidth(0)
        self.btn_clear_cache.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self.btn_clear_cache.clicked.connect(self.on_clear_cache)

        def add_field_pair(label: QtWidgets.QLabel, widget: QtWidgets.QWidget, label_width: int = 0) -> QtWidgets.QHBoxLayout:
            row = QtWidgets.QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            if label_width:
                label.setMinimumWidth(label_width)
            label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Fixed)
            widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            row.addWidget(label, 0)
            row.addWidget(widget, 1)
            return row

        top_label_width = 76
        top.addLayout(add_field_pair(self.lbl_profile, self.edt_profile, top_label_width), 0, 0)
        top.addLayout(add_field_pair(self.lbl_api, self.edt_key, top_label_width), 0, 1)
        top.addLayout(add_field_pair(self.lbl_lang, self.cmb_lang, top_label_width), 1, 0)
        top.addLayout(add_field_pair(self.lbl_performance, self.cmb_performance), 1, 1)

        icons_cache = QtWidgets.QHBoxLayout()
        icons_cache.setContentsMargins(0, 0, 0, 0)
        icons_cache.setSpacing(12)
        icons_cache.addLayout(add_field_pair(self.lbl_icons, self.cmb_icons, top_label_width), 1)
        icons_cache.addWidget(self.btn_clear_cache, 0)
        top.addLayout(icons_cache, 2, 0, 1, 2)

        top.setColumnStretch(0, 1)
        top.setColumnStretch(1, 1)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.btn_fetch)
        actions.addWidget(self.btn_stop)
        actions.addWidget(self.btn_export)
        actions.setStretch(0, 1)
        actions.setStretch(1, 1)
        actions.setStretch(2, 1)

        controls.addSpacing(8)

        self.section_divider = QtWidgets.QFrame()
        self.section_divider.setObjectName("SectionDivider")
        self.section_divider.setFixedHeight(1)
        controls.addWidget(self.section_divider)

        controls.addSpacing(8)

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
        self.cmb_sort.currentIndexChanged.connect(lambda *_: self.refresh_table(update_status=False))

        self.lbl_sorting = QtWidgets.QLabel()
        self.lbl_sorting.setObjectName("FieldLabel")

        self.lbl_n = QtWidgets.QLabel()
        self.lbl_n.setObjectName("FieldLabel")
        self.spin_n = SmartSpinBox()
        self.spin_n.setRange(1, 1440)
        self.spin_n.setValue(2)
        self.spin_n.setFixedWidth(98)
        self.spin_n.valueChanged.connect(lambda *_: self.refresh_table(update_status=False))
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

        controls.addSpacing(8)

        self.actions_divider = QtWidgets.QFrame()
        self.actions_divider.setObjectName("SectionDivider")
        self.actions_divider.setFixedHeight(1)
        controls.addWidget(self.actions_divider)

        controls.addSpacing(8)

        controls.addLayout(actions)

        page.addWidget(controls_card)

        self.btn_toggle_menu = QtWidgets.QToolButton()
        self.btn_toggle_menu.setObjectName("MenuToggleButton")
        self.btn_toggle_menu.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_menu.setArrowType(QtCore.Qt.ArrowType.UpArrow)
        self.btn_toggle_menu.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.btn_toggle_menu.setAutoRaise(False)
        self.btn_toggle_menu.clicked.connect(self.toggle_controls_menu)
        self.btn_toggle_menu.installEventFilter(self)

        toggle_row = QtWidgets.QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.addStretch(1)
        toggle_row.addWidget(self.btn_toggle_menu, 0)
        toggle_row.addStretch(1)
        page.addLayout(toggle_row)

        table_card = QtWidgets.QFrame()
        table_card.setObjectName("TableCard")
        table_l = QtWidgets.QVBoxLayout(table_card)
        table_l.setContentsMargins(0, 0, 0, 0)
        table_l.setSpacing(0)

        self.table_model = AchievementTableModel(self)
        self.table = QuietTable()
        self.table.setObjectName("AchievementTable")
        self.table_v_scroll = CapsuleScrollBar(QtCore.Qt.Orientation.Vertical, self.table)
        self.table_h_scroll = CapsuleScrollBar(QtCore.Qt.Orientation.Horizontal, self.table)
        self.table.setModel(self.table_model)
        self.table.setVerticalScrollBar(self.table_v_scroll)
        self.table.setHorizontalScrollBar(self.table_h_scroll)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setIconSize(QtCore.QSize(34, 34))
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.verticalHeader().setMinimumSectionSize(46)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setGridStyle(QtCore.Qt.PenStyle.SolidLine)
        self.table.setWordWrap(False)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        self.table.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.table.setCornerButtonEnabled(False)
        self.table.setItemDelegate(NoHighlightDelegate(self.table))
        self.table.viewport().installEventFilter(self)
        self.table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.table.setHorizontalHeader(OffsetHeaderView(QtCore.Qt.Orientation.Horizontal, self.table))
        hh = self.table.horizontalHeader()
        hh.setDefaultSectionSize(200)
        hh.setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
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
        self.table_scroll_header.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.table_scroll_header.setAutoFillBackground(True)
        self.table_scroll_header.setStyleSheet("background: #1d2836; border-left: 1px solid #2b3849; border-right: 0px; border-bottom: 1px solid #2b3849; border-top: 0px;")
        pal = self.table_scroll_header.palette()
        pal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor('#1d2836'))
        self.table_scroll_header.setPalette(pal)
        self.table_scroll_header.hide()
        self.table.verticalScrollBar().rangeChanged.connect(lambda *_: (self._apply_compact_table_columns(), self._update_table_scroll_header(), self._schedule_visible_icon_load()))
        self.table.verticalScrollBar().valueChanged.connect(lambda *_: self._schedule_visible_icon_load())
        self.table.horizontalHeader().geometriesChanged.connect(self._refresh_table_geometry)
        self.table.horizontalScrollBar().rangeChanged.connect(lambda *_: self._refresh_table_geometry())

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
            QFrame#SectionDivider {
                background: #243244;
                border: 0px;
                border-radius: 0px;
                min-height: 1px;
                max-height: 1px;
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
                background: #e0b63d;
                border: 1px solid #b88a17;
                color: #111111;
            }
            QPushButton#PrimaryButton:hover {
                background: #f0c955;
                border: 1px solid #c99b28;
                color: #0f0f0f;
            }
            QPushButton#PrimaryButton:pressed {
                background: #cda231;
                border: 1px solid #a6780f;
                color: #101010;
            }
            QPushButton#DangerButton {
                background: #3a2028;
                border: 1px solid #9b4054;
                color: #ffd9df;
            }
            QPushButton#DangerButton:hover {
                background: #542733;
                border: 1px solid #c24a63;
            }
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
            QPushButton#ExportButton {
                background: #183b2d;
                color: #ecfdf5;
                border-color: #2f7d55;
            }
            QPushButton#ExportButton:hover {
                background: #1f6f4a;
                color: #ffffff;
                border-color: #34d399;
            }
            QPushButton#ExportButton:pressed {
                background: #14532d;
                border-color: #2f7d55;
            }
            QPushButton#ExportButton:disabled {
                background: #111827;
                color: #6b7280;
                border-color: #374151;
            }
            QToolButton#MenuToggleButton {
                min-width: 42px;
                min-height: 28px;
                max-width: 42px;
                max-height: 28px;
                border-radius: 14px;
                border: 1px solid #32455f;
                background: #141c27;
                color: #dbe7f3;
                padding: 0px;
            }
            QToolButton#MenuToggleButton:hover {
                background: #182231;
                border: 1px solid #425977;
            }
            QToolButton#MenuToggleButton:pressed {
                background: #101722;
                border: 1px solid #f2c94c;
            }
            QToolButton#MenuToggleButton[dragOutside="true"] {
                background: #141c27;
                border: 1px solid #32455f;
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
            QTableView#AchievementTable {
                background: #111822;
                alternate-background-color: #141d29;
                color: #dce8f3;
                border: 0px;
                border-bottom: 0px;
                border-radius: 0px;
                gridline-color: #243142;
            }
            QTableView#AchievementTable::item {
                padding: 7px;
                border: 0px;
            }
            QTableView#AchievementTable::item:selected {
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
                border-left: 1px solid #2b3849;
                border-right: 0px;
                border-bottom: 1px solid #2b3849;
                border-top: 0px;
                margin: 0px;
                padding: 0px;
            }
            QTableView#AchievementTable QScrollBar:vertical {
                background: transparent;
                border: none;
                width: 16px;
                margin: 0px;
            }
            QTableView#AchievementTable QScrollBar:horizontal {
                background: transparent;
                border: none;
                height: 16px;
                margin: 0px;
            }
            QTableView#AchievementTable QScrollBar::handle:vertical,
            QTableView#AchievementTable QScrollBar::handle:horizontal,
            QTableView#AchievementTable QScrollBar::add-line:vertical,
            QTableView#AchievementTable QScrollBar::sub-line:vertical,
            QTableView#AchievementTable QScrollBar::add-line:horizontal,
            QTableView#AchievementTable QScrollBar::sub-line:horizontal,
            QTableView#AchievementTable QScrollBar::add-page:vertical,
            QTableView#AchievementTable QScrollBar::sub-page:vertical,
            QTableView#AchievementTable QScrollBar::add-page:horizontal,
            QTableView#AchievementTable QScrollBar::sub-page:horizontal {
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

    def _set_toggle_button_drag_outside(self, value: bool) -> None:
        if not hasattr(self, "btn_toggle_menu"):
            return
        if self.btn_toggle_menu.property("dragOutside") == value:
            return
        self.btn_toggle_menu.setProperty("dragOutside", value)
        self.btn_toggle_menu.style().unpolish(self.btn_toggle_menu)
        self.btn_toggle_menu.style().polish(self.btn_toggle_menu)
        self.btn_toggle_menu.update()

    def _reset_api_key_view_to_start(self) -> None:
        if not hasattr(self, "edt_key"):
            return
        if self.edt_key.hasSelectedText():
            return
        self.edt_key.setCursorPosition(0)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if hasattr(self, "edt_key") and obj is self.edt_key:
            event_type = event.type()
            if event_type in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.FocusOut):
                QtCore.QTimer.singleShot(0, self._reset_api_key_view_to_start)

        if hasattr(self, "btn_toggle_menu") and obj is self.btn_toggle_menu:
            event_type = event.type()
            if event_type == QtCore.QEvent.Type.MouseButtonPress:
                self._toggle_button_pressed = True
                self._set_toggle_button_drag_outside(False)
            elif event_type == QtCore.QEvent.Type.MouseMove and self._toggle_button_pressed:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                self._set_toggle_button_drag_outside(not self.btn_toggle_menu.rect().contains(pos))
            elif event_type in (QtCore.QEvent.Type.Leave, QtCore.QEvent.Type.HoverLeave) and self._toggle_button_pressed:
                self._set_toggle_button_drag_outside(True)
            elif event_type == QtCore.QEvent.Type.MouseButtonRelease:
                self._toggle_button_pressed = False
                QtCore.QTimer.singleShot(0, lambda: self._set_toggle_button_drag_outside(False))

        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            self._clear_control_focus_on_background_click(obj)

        if hasattr(self, "table") and obj is self.table.viewport():
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
        self._schedule_visible_icon_load()

    def showEvent(self, event: QtGui.QShowEvent):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._refresh_table_geometry)
        QtCore.QTimer.singleShot(50, self._refresh_table_geometry)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._refresh_table_geometry)

    def toggle_controls_menu(self):
        if not hasattr(self, "controls_card") or not hasattr(self, "btn_toggle_menu"):
            return
        if self._menu_animating:
            return

        focused = QtWidgets.QApplication.focusWidget()
        if focused and focused.window() is self:
            focused.clearFocus()

        self._menu_animating = True
        self.btn_toggle_menu.setEnabled(False)
        self.controls_card.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        if self._menu_animation_group is not None:
            with suppress(RuntimeError):
                if self._menu_animation_group.state() == QtCore.QAbstractAnimation.State.Running:
                    self._menu_animation_group.stop()
                self._menu_animation_group.deleteLater()
            self._menu_animation_group = None

        expanded_height = max(self.controls_card.sizeHint().height(), self.controls_card.layout().sizeHint().height())
        end_collapsed = not self._menu_collapsed

        if end_collapsed:
            start_height = max(self.controls_card.height(), expanded_height)
            end_height = 0
            start_opacity = 1.0
            end_opacity = 0.0
        else:
            self.controls_card.show()
            self.controls_card.setMaximumHeight(0)
            start_height = 0
            end_height = expanded_height
            start_opacity = 0.0
            end_opacity = 1.0

        opacity_effect = self.controls_card.graphicsEffect()
        if not isinstance(opacity_effect, QtWidgets.QGraphicsOpacityEffect):
            opacity_effect = QtWidgets.QGraphicsOpacityEffect(self.controls_card)
            self.controls_card.setGraphicsEffect(opacity_effect)
        opacity_effect.setOpacity(start_opacity)

        height_anim = QtCore.QPropertyAnimation(self.controls_card, b"maximumHeight", self)
        height_anim.setDuration(220)
        height_anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutCubic)
        height_anim.setStartValue(start_height)
        height_anim.setEndValue(end_height)

        opacity_anim = QtCore.QPropertyAnimation(opacity_effect, b"opacity", self)
        opacity_anim.setDuration(180)
        opacity_anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutQuad)
        opacity_anim.setStartValue(start_opacity)
        opacity_anim.setEndValue(end_opacity)

        group = QtCore.QParallelAnimationGroup(self)
        group.addAnimation(height_anim)
        group.addAnimation(opacity_anim)

        def finalize():
            self._menu_collapsed = end_collapsed
            if self._menu_collapsed:
                self.controls_card.setMaximumHeight(0)
                self.controls_card.hide()
                self.btn_toggle_menu.setArrowType(QtCore.Qt.ArrowType.DownArrow)
            else:
                self.controls_card.show()
                self.controls_card.setMaximumHeight(16777215)
                opacity_effect.setOpacity(1.0)
                self.btn_toggle_menu.setArrowType(QtCore.Qt.ArrowType.UpArrow)
            self.controls_card.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.btn_toggle_menu.setEnabled(True)
            self._menu_animating = False
            self._menu_animation_group = None
            group.deleteLater()

        group.finished.connect(finalize)
        self._menu_animation_group = group
        group.start()

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
            elif col != 3:
                hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, width)

        viewport_width = self.table.viewport().width()
        total_base = sum(base_widths)
        vbar = self.table.verticalScrollBar()
        has_vertical_scroll = self.table.rowCount() > 0 and vbar.maximum() > 0
        desired_policy = (
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if has_vertical_scroll
            else QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        if self.table.verticalScrollBarPolicy() != desired_policy:
            self.table.setVerticalScrollBarPolicy(desired_policy)
            viewport_width = self.table.viewport().width()

        if viewport_width >= total_base:
            hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(3, base_widths[3] + (viewport_width - total_base))
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
        x = max(0, self.table.width() - sb_geo.width() + 1)
        y = hdr_geo.y()
        w = sb_geo.width() + 2
        h = hdr_geo.height()
        self.table_scroll_header.setGeometry(x, y, w, h)
        self.table_scroll_header.show()
        self.table_scroll_header.raise_()
        self.table_scroll_header.update()

    def _retranslate_ui(self):
        t = self.i18n.t
        self.setWindowTitle(t("app_title"))
        self.lbl_title.setText(t("app_title"))
        self.lbl_subtitle.setText(t("subtitle"))
        self.lbl_profile.setText(t("profile") + ":")
        self.edt_profile.setPlaceholderText(t("profile_ph"))
        self.lbl_api.setText(t("api_key") + ":")
        self.edt_key.setPlaceholderText(t("api_key_ph"))
        self.lbl_lang.setText(t("language") + ":")
        self.lbl_performance.setText(t("performance_label") + ":")
        perf_value = self.cmb_performance.currentData() or self.performance_mode
        self.cmb_performance.blockSignals(True)
        self.cmb_performance.clear()
        self.cmb_performance.addItem(t("perf_auto"), userData="auto")
        self.cmb_performance.addItem(t("perf_eco"), userData="eco")
        self.cmb_performance.addItem(t("perf_fast"), userData="fast")
        perf_index = self.cmb_performance.findData(perf_value)
        self.cmb_performance.setCurrentIndex(max(0, perf_index))
        self.cmb_performance.blockSignals(False)
        self.lbl_icons.setText(t("icons_label") + ":")
        icons_value = self.cmb_icons.currentData()
        if icons_value is None:
            icons_value = self.icons_enabled
        self.cmb_icons.blockSignals(True)
        self.cmb_icons.clear()
        self.cmb_icons.addItem(t("icons_on"), userData=True)
        self.cmb_icons.addItem(t("icons_off"), userData=False)
        icons_index = self.cmb_icons.findData(bool(icons_value))
        self.cmb_icons.setCurrentIndex(max(0, icons_index))
        self.cmb_icons.blockSignals(False)
        self.btn_fetch.setText(t("load"))
        self.btn_stop.setText(t("stop"))
        self.btn_export.setText(t("export_csv").replace("…", ""))
        self._update_cache_button_text(force=True)
        self.lbl_game.setText(t("game") + ":")
        self.cmb_sort.blockSignals(True)
        self.cmb_sort.clear()
        self.cmb_sort.addItems([t("sort_desc"), t("sort_asc")])
        self.cmb_sort.blockSignals(False)
        self.lbl_sorting.setText(t("sort_label") + ":")
        self.lbl_n.setText(t("n_label"))
        self.lbl_n_unit.setText(t("min_unit"))
        self.lbl_filters.setText(t("filters_label") + ":")
        self.chk_only_susp.setText(t("only_susp"))
        self.chk_only_exact.setText(t("only_exact"))
        self.btn_reset.setText(t("reset"))
        self.table_model.set_headers(
            [t("hdr_icon"), t("hdr_game"), t("hdr_ach"), t("hdr_desc"), t("hdr_time"), t("hdr_delta"), "⚠"]
        )
        self._render_status()
        self.cmb_game.blockSignals(True)
        if self.cmb_game.count() == 0:
            self.cmb_game.addItem(t("all_games"), userData=None)
        else:
            self.cmb_game.setItemText(0, t("all_games"))
        self.cmb_game.blockSignals(False)

    def _set_status(self, key: str, **kwargs):
        self._status_key = key
        self._status_kwargs = dict(kwargs)
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
        self._clear_input_selection_after_dialog()

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
            lambda msg, w=lgw: (self._safe_remove_worker(w), self.on_error(msg))
        )
        self.threadpool.start(lgw)

    def _safe_remove_worker(self, w: QtCore.QRunnable):
        with suppress(ValueError):
            self._workers.remove(w)

    def on_stop(self):
        if not self._export_blocked_until_ready:
            ThemedMessageDialog.warning(self, self.i18n.t("warning"), self.i18n.t("stop_not_loading"))
            self._clear_input_selection_after_dialog()
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
        self.cmb_game.blockSignals(False)

        self._game_queue = deque(games)
        self._active_workers = 0
        self._start_next_jobs()

    def _start_next_jobs(self):
        while (not self.cancel_event.is_set()) and self._game_queue and (self._active_workers < self.max_workers):
            g = self._game_queue.popleft()
            worker = GameFetchWorker(self.current_api_key, self.current_steamid, g, self.cancel_event)
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

        if self.loaded_games >= self.total_games:
            self._finalize_loading(completed=True)
            return

        if self.cancel_event.is_set() and self._active_workers == 0:
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

    def _load_icon_from_disk_cache(self, url: str) -> bool:
        if not url or url in self.icon_cache:
            return bool(url in self.icon_cache)
        data = read_icon_bytes(url)
        if not data:
            return False
        pix = QtGui.QPixmap()
        if not pix.loadFromData(data):
            return False
        self.icon_cache[url] = QtGui.QIcon(pix)
        return True

    def _enqueue_icon_url(self, url: str, *, front: bool = False) -> None:
        if not url:
            return
        if url not in self.icon_cache and self._load_icon_from_disk_cache(url):
            self._apply_loaded_icon_to_table(url)
            return
        if url in self.icon_cache or url in self.icon_downloading or url in self._pending_icon_url_set:
            return
        if front:
            self._pending_icon_urls.appendleft(url)
        else:
            self._pending_icon_urls.append(url)
        self._pending_icon_url_set.add(url)

    def _schedule_visible_icon_load(self) -> None:
        if self.icons_enabled and hasattr(self, "visible_icon_timer") and not self.visible_icon_timer.isActive():
            self.visible_icon_timer.start()

    def _queue_visible_icons(self):
        if not self.icons_enabled or self.table.rowCount() <= 0:
            return

        viewport = self.table.viewport()
        first = self.table.rowAt(0)
        last = self.table.rowAt(max(0, viewport.height() - 1))
        if first < 0:
            first = 0
        if last < 0:
            last = min(self.table.rowCount() - 1, first + 40)

        first = max(0, first - 10)
        last = min(self.table.rowCount() - 1, last + 10)
        for row in range(first, last + 1):
            self._enqueue_icon_url(self.table_model.icon_url_at(row), front=True)
        self._kick_icon_prefetch()

    def _stop_icon_downloads(self):
        self._pending_icon_urls.clear()
        self._pending_icon_url_set.clear()
        for reply in list(self.icon_replies.values()):
            if reply.isRunning():
                reply.abort()
        self.icon_replies.clear()
        self.icon_downloading.clear()

    def _kick_icon_prefetch(self):
        if not self.icons_enabled:
            self._pending_icon_urls.clear()
            self._pending_icon_url_set.clear()
            return

        while self._pending_icon_urls and len(self.icon_downloading) < self.max_icon_downloads:
            url = self._pending_icon_urls.popleft()
            self._pending_icon_url_set.discard(url)
            if url in self.icon_cache or url in self.icon_downloading:
                continue
            self.icon_downloading.add(url)
            req = QNetworkRequest(QtCore.QUrl(url))
            reply = self.net.get(req)
            self.icon_replies[url] = reply

    def _apply_loaded_icon_to_table(self, url: str) -> None:
        icon = self.icon_cache.get(url)
        if not icon:
            return
        rows = self.table_model.set_icon_for_url(url, icon)
        if rows:
            self.table.viewport().update()

    def _on_icon_loaded(self, reply: QNetworkReply):
        url = reply.url().toString()
        loaded = False
        try:
            self.icon_replies.pop(url, None)
            if self.icons_enabled and reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll().data()
                pix = QtGui.QPixmap()
                if pix.loadFromData(data):
                    self.icon_cache[url] = QtGui.QIcon(pix)
                    write_icon_bytes(url, data)
                    self._update_cache_button_text(force=True)
                    loaded = True
        finally:
            reply.deleteLater()
            self.icon_downloading.discard(url)
            if loaded:
                self._apply_loaded_icon_to_table(url)
            self._queue_visible_icons()

    def _finalize_loading(self, completed: bool = False, stopped: bool = False):
        self._export_blocked_until_ready = False
        self._loading_game_list = False
        self.btn_fetch.setEnabled(True)
        self.btn_stop.setEnabled(False)

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

    def on_error(self, message: str):
        self._loading_game_list = False
        self._finalize_loading()
        self._set_status("error")
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

    def _analysis_signature_for_items(self, items: List[Achievement]) -> tuple:
        return tuple((id(a), int(a.unlock_time or 0)) for a in items)

    def _analysis_maps_for_items(self, items: List[Achievement]) -> tuple[Dict[int, Optional[int]], Dict[int, int]]:
        signature = self._analysis_signature_for_items(items)
        if signature == self._analysis_cache_signature:
            return self._analysis_cache_deltas, self._analysis_cache_exact_count

        delta_by_id = self._delta_map_ascending(items)
        exact_count: Dict[int, int] = {}
        for a in items:
            if a.unlock_time:
                exact_count[a.unlock_time] = exact_count.get(a.unlock_time, 0) + 1

        self._analysis_cache_signature = signature
        self._analysis_cache_deltas = delta_by_id
        self._analysis_cache_exact_count = exact_count
        return delta_by_id, exact_count

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

    def _format_delta_seconds(self, seconds: Optional[int], dash: Optional[str] = None) -> str:
        if seconds is None:
            return dash if dash is not None else self.i18n.t("dash")
        mins = seconds // 60
        secs = seconds % 60
        if mins > 0:
            return self.i18n.fmt("mins_secs_fmt", m=mins, s=secs)
        return self.i18n.fmt("secs_fmt", s=secs)

    def refresh_table(self, *args, update_status: bool = True):
        t = self.i18n
        items = self._filtered_sorted()
        self.table.setUpdatesEnabled(False)
        self._icon_rows.clear()

        source_items = self._base_items()
        delta_by_id, exact_count = self._analysis_maps_for_items(source_items)

        n_sec_threshold = self.spin_n.value() * 60
        dash = t.t("dash")

        rows = []
        for a in items:
            icon_url = a.icon_url or ""
            icon = self.icon_cache.get(icon_url) if self.icons_enabled else None
            if icon_url:
                self._icon_rows.setdefault(icon_url, []).append(len(rows))

            dt = a.unlock_dt()
            ts_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else dash

            d = delta_by_id.get(id(a))
            if d is None or not a.unlock_time:
                delta_str = dash
                delta_ok = False
            else:
                delta_str = self._format_delta_seconds(d, dash=dash)
                delta_ok = d <= max(1, n_sec_threshold)

            is_exact_dup = bool(a.unlock_time and exact_count.get(a.unlock_time, 0) >= 2)
            suspicious = is_exact_dup or (delta_str != dash and delta_ok)

            rows.append({
                "texts": [
                    "",
                    a.game_name,
                    self._achievement_display_name(a),
                    self._achievement_display_description(a),
                    ts_str,
                    delta_str,
                    "⚠" if suspicious else "",
                ],
                "icon_url": icon_url,
                "icon": icon,
                "suspicious": suspicious,
                "delta_bold": suspicious,
            })

        self.table_model.set_rows(rows)
        self._apply_compact_table_columns()
        self.table.setUpdatesEnabled(True)
        QtCore.QTimer.singleShot(0, self._refresh_table_geometry)
        self._schedule_visible_icon_load()

        if update_status and not self._export_blocked_until_ready:
            self._set_status("shown", n=self.table.rowCount())
        self._update_table_scroll_header()

    def reset_filters(self):
        view_changed = (
            self.cmb_sort.currentIndex() != 0
            or self.spin_n.value() != 2
        )
        filter_changed = (
            self.cmb_game.currentIndex() != 0
            or self.chk_only_susp.isChecked()
            or self.chk_only_exact.isChecked()
        )
        changed = view_changed or filter_changed

        controls = (
            self.cmb_game,
            self.cmb_sort,
            self.spin_n,
            self.chk_only_susp,
            self.chk_only_exact,
        )
        for control in controls:
            control.blockSignals(True)

        self.cmb_game.setCurrentIndex(0)
        self.cmb_sort.setCurrentIndex(0)
        self.spin_n.setValue(2)
        self.chk_only_susp.setChecked(False)
        self.chk_only_exact.setChecked(False)

        for control in controls:
            control.blockSignals(False)

        if changed:
            self.refresh_table(update_status=filter_changed)

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
        return self._csv_text(value)

    def _csv_filename_identifier(self) -> str:
        profile = (self.current_profile_url or self.edt_profile.text() or "").strip().rstrip("/")
        identifier = ""

        if "/id/" in profile:
            identifier = profile.split("/id/", 1)[1].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
        elif profile and "/profiles/" not in profile and not profile.isdigit():
            identifier = profile.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]

        if not identifier:
            identifier = self.current_steamid or profile or "profile"

        safe = []
        for ch in identifier:
            if ch.isalnum() or ch in ("-", "_", "."):
                safe.append(ch)
            else:
                safe.append("_")
        cleaned = "".join(safe).strip("._-")
        return cleaned or "profile"

    def _csv_default_filename(self) -> str:
        localized_names = {
            "ru": "достижения",
            "zh_CN": "成就",
            "es": "logros",
            "pt_BR": "conquistas",
            "de": "erfolge",
            "fr": "succes",
            "ja": "実績",
            "ko": "도전과제",
        }
        base_name = localized_names.get(self.i18n.lang, "achievements")
        return f"{base_name}_{self._csv_filename_identifier()}.csv"

    def export_csv(self):
        t = self.i18n.t
        if self._export_blocked_until_ready:
            ThemedMessageDialog.warning(self, t("warning"), t("export_loading"))
            self._clear_input_selection_after_dialog()
            return
        if self.table.rowCount() == 0:
            ThemedMessageDialog.information(self, t("info"), t("export_none"))
            self._clear_input_selection_after_dialog()
            return

        default_path = os.path.join(app_exports_dir(), self._csv_default_filename())
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("save_csv"),
                                                        default_path, "CSV (*.csv)")
        if not path:
            self._clear_input_selection_after_dialog()
            return

        exported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game_filter = self.cmb_game.currentText() or t("all_games")
        sort_label = self.cmb_sort.currentText()
        threshold_text = self._threshold_label()
        only_susp = t("toggle_on") if self.chk_only_susp.isChecked() else t("toggle_off")
        only_exact = t("toggle_on") if self.chk_only_exact.isChecked() else t("toggle_off")

        def write_csv(to_path: str):
            items = self._filtered_sorted()
            source_items = self._base_items()
            delta_by_id, exact_count = self._analysis_maps_for_items(source_items)

            n_sec_threshold = self.spin_n.value() * 60
            dash = t("dash")

            with open(to_path, "w", newline="", encoding="utf-16", errors="strict") as f:
                export_title = t("export_title")
                exported_label = t("exported")
                profile_label = t("profile")
                ui_language_label = t("ui_language")
                game_filter_label = t("game_filter")
                sort_label_name = t("sort_label")
                threshold_label = t("threshold")
                only_suspicious_label = t("only_suspicious_filter")
                only_exact_label = t("only_exact_filter")

                f.write(f"# {self._csv_text(export_title)}\n")
                f.write(f"# {self._csv_text(exported_label)}: {self._csv_text(exported_at)}\n")
                f.write(f"# {self._csv_text(profile_label)}: {self._csv_text(self.current_profile_url)}\n")
                f.write(f"# {self._csv_text(ui_language_label)}: {self._csv_text(self.i18n.lang)}\n")
                f.write(f"# {self._csv_text(game_filter_label)}: {self._csv_text(game_filter)}\n")
                f.write(f"# {self._csv_text(sort_label_name)}: {self._csv_text(sort_label)}\n")
                f.write(f"# {self._csv_text(threshold_label)}: {self._csv_text(threshold_text)}\n")
                f.write(f"# {self._csv_text(only_suspicious_label)}: {self._csv_text(only_susp)}\n")
                f.write(f"# {self._csv_text(only_exact_label)}: {self._csv_text(only_exact)}\n")

                w = csv.writer(f, delimiter="\t", lineterminator="\n")
                w.writerow([
                    self._csv_text(t("hdr_game")),
                    self._csv_text(t("hdr_ach")),
                    self._csv_text(t("hdr_desc")),
                    self._csv_text(t("hdr_time")),
                    self._csv_text(t("export_hdr_delta")),
                    self._csv_text(t("hdr_suspicious")),
                ])

                for a in items:
                    dt = a.unlock_dt()
                    ts_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else dash
                    d = delta_by_id.get(id(a))
                    if d is None or not a.unlock_time:
                        delta_str = dash
                        delta_ok = False
                    else:
                        delta_str = self._format_delta_seconds(d, dash=dash)
                        delta_ok = d <= max(1, n_sec_threshold)
                    is_exact_dup = bool(a.unlock_time and exact_count.get(a.unlock_time, 0) >= 2)
                    suspicious = is_exact_dup or (delta_str != dash and delta_ok)

                    w.writerow([
                        self._csv_text(a.game_name),
                        self._csv_text(self._achievement_display_name(a)),
                        self._csv_text(self._achievement_display_description(a)),
                        self._csv_text(ts_str),
                        self._csv_delta_text(delta_str),
                        self._csv_text(t("susp_yes")) if suspicious else "",
                    ])

        try:
            write_csv(path)
        except PermissionError:
            base, ext = os.path.splitext(path)
            alt = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext or '.csv'}"
            ThemedMessageDialog.warning(
                self, self.i18n.t("error"),
                self.i18n.t("export_permission_denied")
            )
            new_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("save_csv"), alt, "CSV (*.csv)")
            if new_path:
                write_csv(new_path)
            else:
                self._clear_input_selection_after_dialog()
                return

        ThemedMessageDialog.information(self, t("info"), t("export_done"))
        self._clear_input_selection_after_dialog()