import os
import threading
from collections import deque
from typing import Deque, Dict, List, Optional, Set

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply

from sai.core.i18n import I18n
from sai.core.models import Achievement
from sai.core.paths import resource_path
from sai.storage.cache import cleanup_cache
from sai.ui.main_window.analysis import AnalysisMixin
from sai.ui.main_window.events import EventsMixin
from sai.ui.main_window.export import ExportMixin
from sai.ui.main_window.icons import IconsMixin
from sai.ui.main_window.loading import LoadingMixin
from sai.ui.main_window.performance import PerformanceMixin
from sai.ui.main_window.setup import SetupMixin
from sai.ui.main_window.state import StateMixin


class MainWindow(ExportMixin, AnalysisMixin, IconsMixin, LoadingMixin, StateMixin, EventsMixin, SetupMixin, PerformanceMixin, QtWidgets.QMainWindow):

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
        self._load_error_reported = False

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