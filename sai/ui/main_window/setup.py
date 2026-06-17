from PyQt6 import QtCore, QtGui, QtWidgets

from sai.core.i18n import I18n
from sai.ui.delegates import NoHighlightDelegate, OffsetHeaderView
from sai.ui.scrollbars import CapsuleScrollBar
from sai.ui.widgets import CustomComboBox, FocusAwareCheckBox, QuietTable, RoundedProgressBar, SmartSpinBox, StyledClearLineEdit
from sai.ui.table_model import AchievementTableModel

class SetupMixin:

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
        self.edt_key.secretRevealRequested.connect(self._confirm_api_key_reveal_from_enter)

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
        self.btn_fetch.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.btn_fetch.clicked.connect(self.on_fetch)

        self.btn_stop = QtWidgets.QPushButton()
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.btn_stop.clicked.connect(self.on_stop)

        self.btn_export = QtWidgets.QPushButton()
        self.btn_export.setObjectName("ExportButton")
        self.btn_export.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.btn_export.clicked.connect(self.export_csv)

        self.btn_clear_cache = QtWidgets.QPushButton()
        self.btn_clear_cache.setObjectName("GhostButton")
        self.btn_clear_cache.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
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
        self.cmb_game.setObjectName("GameCombo")
        self.cmb_game.addItem("", userData=None)
        self.cmb_game.setEnabled(False)
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

        self.chk_only_susp = FocusAwareCheckBox()
        self.chk_only_susp.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.chk_only_susp.stateChanged.connect(self.refresh_table)

        self.chk_only_exact = FocusAwareCheckBox()
        self.chk_only_exact.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.chk_only_exact.stateChanged.connect(self.refresh_table)

        self.lbl_filters = QtWidgets.QLabel()
        self.lbl_filters.setObjectName("FieldLabel")

        self.btn_reset = QtWidgets.QPushButton()
        self.btn_reset.setObjectName("GhostButton")
        self.btn_reset.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
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
        self.btn_toggle_menu.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
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
            QComboBox#GameCombo:disabled {
                background: #0b111a;
                color: #6b7b8e;
                border: 1px solid #1f2b3a;
            }
            QComboBox#GameCombo::drop-down:disabled {
                background: transparent;
            }
            QComboBox#GameCombo::down-arrow:disabled {
                background: #3d4b5d;
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
                outline: 0px;
            }
            QPushButton:hover { background: #263448; }
            QPushButton:pressed { background: #182231; }
            QPushButton:focus {
                border: 2px solid #f2c94c;
                padding: 7px 11px;
                background: #263448;
            }
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
            QPushButton#PrimaryButton:focus {
                background: #f0c955;
                border: 2px solid #fff0a6;
                color: #0f0f0f;
                padding: 7px 11px;
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
            QPushButton#DangerButton:focus {
                background: #542733;
                border: 2px solid #ff6f87;
                padding: 7px 11px;
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
            QPushButton#GhostButton:focus {
                background: #18212d;
                color: #ffd34d;
                border: 2px solid #f2c94c;
                padding: 7px 11px;
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
            QPushButton#ExportButton:focus {
                background: #1f6f4a;
                color: #ffffff;
                border: 2px solid #6ee7a8;
                padding: 7px 11px;
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
                outline: 0px;
            }
            QToolButton#MenuToggleButton:hover {
                background: #182231;
                border: 1px solid #425977;
            }
            QToolButton#MenuToggleButton:pressed {
                background: #101722;
                border: 1px solid #f2c94c;
            }
            QToolButton#MenuToggleButton:focus {
                background: #1b2635;
                border: 2px solid #f2c94c;
            }
            QToolButton#MenuToggleButton[dragOutside="true"] {
                background: #141c27;
                border: 1px solid #32455f;
            }
            QCheckBox {
                color: #dbe7f3;
                spacing: 8px;
                font-weight: 600;
                outline: 0px;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 3px 7px 3px 8px;
            }
            QCheckBox:hover {
                color: #f8fdff;
                background: transparent;
                border: 1px solid transparent;
            }
            QCheckBox[tabFocus="true"] {
                color: #f8fdff;
                background: transparent;
                border: 2px solid #f2c94c;
                padding: 2px 6px 2px 7px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 6px;
                border: 1px solid #3a4a5f;
                background: #101722;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #50647d;
                background: #152131;
            }
            QCheckBox::indicator:checked {
                background: #e0b63d;
                border: 1px solid #ffd666;
            }
            QCheckBox[tabFocus="true"]::indicator {
                border: 1px solid #3a4a5f;
                background: #101722;
            }
            QCheckBox[tabFocus="true"]::indicator:checked {
                background: #e0b63d;
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