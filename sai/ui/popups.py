from typing import Callable, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

API_KEY_URL = "https://steamcommunity.com/dev/apikey"


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


class ContextMenuRow(QtWidgets.QFrame):
    triggered = QtCore.pyqtSignal()

    def __init__(self, title: str, shortcut: str = "", enabled: bool = True, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ContextMenuRow")
        self.setProperty("hovered", False)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
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
        self.title_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.shortcut_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.shortcut_label)

    def set_hovered(self, hovered: bool) -> None:
        hovered = bool(hovered and self.isEnabled())
        if self.property("hovered") == hovered:
            return
        self.setProperty("hovered", hovered)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _notify_menu_hover(self) -> None:
        menu = self.window()
        if hasattr(menu, "_set_hovered_row"):
            menu._set_hovered_row(self if self.isEnabled() else None)
        else:
            self.set_hovered(True)

    def enterEvent(self, event: QtCore.QEvent) -> None:
        self._notify_menu_hover()
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        menu = self.window()
        if hasattr(menu, "_sync_hovered_from_cursor"):
            menu._sync_hovered_from_cursor()
        else:
            self.set_hovered(False)
        super().leaveEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        self._notify_menu_hover()
        super().mouseMoveEvent(event)

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

        self._rows: list[ContextMenuRow] = []
        self._hovered_row: Optional[ContextMenuRow] = None
        self.setMouseTracking(True)
        self.panel.setMouseTracking(True)

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
            QFrame#ContextMenuRow[hovered="true"] {
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
            QFrame#ContextMenuRow[hovered="true"] QLabel#ContextMenuRowTitle,
            QFrame#ContextMenuRow[hovered="true"] QLabel#ContextMenuRowShortcut {
                color: #ffffff;
            }
            """
        )

    def _selected_range(self) -> tuple[int, int]:
        start = self.target.selectionStart()
        text = self.target.selectedText()
        if start < 0 or not text:
            return -1, 0
        return start, len(text)

    def _copy_selected_text(self) -> None:
        start, length = self._selected_range()
        if start >= 0 and length > 0:
            QtWidgets.QApplication.clipboard().setText(self.target.text()[start:start + length])

    def _cut_selected_text(self) -> None:
        if self.target.isReadOnly():
            return
        self._copy_selected_text()
        self.target.del_()

    def _clear_actions(self) -> None:
        self._hovered_row = None
        self._rows.clear()
        while self.layout_.count():
            item = self.layout_.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _set_hovered_row(self, row: Optional[ContextMenuRow]) -> None:
        if row is not None and (row not in self._rows or not row.isEnabled()):
            row = None
        if row is self._hovered_row:
            return
        old_row = self._hovered_row
        self._hovered_row = row
        if old_row is not None:
            old_row.set_hovered(False)
        if row is not None:
            row.set_hovered(True)

    def _sync_hovered_from_cursor(self) -> None:
        global_pos = QtGui.QCursor.pos()
        hovered = None
        for row in self._rows:
            local_pos = row.mapFromGlobal(global_pos)
            if row.isVisible() and row.isEnabled() and row.rect().contains(local_pos):
                hovered = row
                break
        self._set_hovered_row(hovered)

    def _add_action(self, title: str, shortcut: str, enabled: bool, callback: Callable[[], None]):
        row = ContextMenuRow(title, shortcut, enabled, self.panel)
        if enabled:
            row.triggered.connect(lambda cb=callback: (cb(), self.hide()))
        self._rows.append(row)
        self.layout_.addWidget(row)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        self._sync_hovered_from_cursor()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        self._sync_hovered_from_cursor()
        super().leaveEvent(event)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        self._set_hovered_row(None)
        super().hideEvent(event)

    def popup(self, global_pos: QtCore.QPoint):
        self._clear_actions()
        clipboard = QtWidgets.QApplication.clipboard().text()
        has_selection = bool(self.target.selectedText())
        read_only = self.target.isReadOnly()

        self._add_action("Undo", "Ctrl+Z", (not read_only) and self.target.isUndoAvailable(), self.target.undo)
        self._add_action("Redo", "Ctrl+Y", (not read_only) and self.target.isRedoAvailable(), self.target.redo)
        self._add_action("Cut", "Ctrl+X", (not read_only) and has_selection, self._cut_selected_text)
        self._add_action("Copy", "Ctrl+C", has_selection, self._copy_selected_text)
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
        QtCore.QTimer.singleShot(0, self._sync_hovered_from_cursor)


class ThemedMessageDialog(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget], title: str, message: str, kind: str = "info", show_cancel: bool = False, ok_text: Optional[str] = None, cancel_text: Optional[str] = None, dangerous_ok: bool = False, show_copy: bool = False):
        super().__init__(parent)
        self._result = 0
        self._loop: Optional[QtCore.QEventLoop] = None
        self._title = title
        self._message = message
        self._kind = kind
        self._show_cancel = show_cancel
        self._ok_text = ok_text
        self._cancel_text = cancel_text
        self._dangerous_ok = dangerous_ok
        self._show_copy = show_copy
        self._copy_link_url = API_KEY_URL if API_KEY_URL in str(message or "") else None
        self._focus_widgets = []
        self._initial_focus_widget: Optional[QtWidgets.QWidget] = None
        self._app_filter_installed = False

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
        self.title_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
        self.title_label.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        title_row.addWidget(self.title_label, 1)

        close_btn = QtWidgets.QPushButton("×")
        close_btn.setObjectName("DialogCloseButton")
        close_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        close_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.reject)
        self._register_focus_widget(close_btn)
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
        self.message_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
        self.message_label.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.message_label.setMinimumWidth(240)
        content_row.addWidget(self.message_label, 1)
        body_layout.addLayout(content_row)

        buttons_row = QtWidgets.QHBoxLayout()
        if kind == "error" and self._show_copy:
            copy_text = "Copy"
            if parent is not None and hasattr(parent, "i18n"):
                copy_text = parent.i18n.t("copy")
            copy_btn = QtWidgets.QPushButton(copy_text)
            copy_btn.setObjectName("DialogOkButton")
            copy_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            copy_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
            copy_btn.setFixedHeight(42)
            copy_btn.setMinimumWidth(104)
            copy_btn.clicked.connect(self._copy_message)
            self._register_focus_widget(copy_btn)
            buttons_row.addWidget(copy_btn)
        if kind == "error" and self._copy_link_url:
            copy_link_text = "Copy link"
            if parent is not None and hasattr(parent, "i18n"):
                copy_link_text = parent.i18n.t("copy_link")
            copy_link_btn = QtWidgets.QPushButton(copy_link_text)
            copy_link_btn.setObjectName("DialogOkButton")
            copy_link_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            copy_link_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
            copy_link_btn.setFixedHeight(42)
            copy_link_btn.setMinimumWidth(104)
            copy_link_btn.clicked.connect(self._copy_link)
            self._register_focus_widget(copy_link_btn)
            buttons_row.addWidget(copy_link_btn)
        buttons_row.addStretch(1)
        if self._show_cancel:
            cancel_btn = QtWidgets.QPushButton(self._cancel_text or "Cancel")
            cancel_btn.setObjectName("DialogOkButton")
            cancel_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            cancel_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
            cancel_btn.setFixedHeight(42)
            cancel_btn.setMinimumWidth(104)
            cancel_btn.clicked.connect(self.reject)
            self._register_focus_widget(cancel_btn)
            self._initial_focus_widget = cancel_btn
            buttons_row.addWidget(cancel_btn)
        ok_btn = QtWidgets.QPushButton(self._ok_text or "OK")
        ok_btn.setObjectName("DialogDangerButton" if self._dangerous_ok else "DialogOkButton")
        ok_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        ok_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        ok_btn.setFixedHeight(42)
        ok_btn.setMinimumWidth(104)
        ok_btn.clicked.connect(self.accept)
        self._register_focus_widget(ok_btn)
        if self._initial_focus_widget is None:
            self._initial_focus_widget = ok_btn
        buttons_row.addWidget(ok_btn)
        body_layout.addLayout(buttons_row)
        self._normalize_focus_order()

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
                padding-left: 0;
                padding-right: 0;
                padding-top: 0;
                padding-bottom: 3px;
            }
            QPushButton#DialogCloseButton:hover, QPushButton#DialogCloseButton:focus {
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
            QPushButton#DialogOkButton:hover, QPushButton#DialogOkButton:focus {
                background: #263448;
                border: 1px solid #4d6f95;
            }
            QPushButton#DialogOkButton:pressed { background: #182231; }
            QPushButton#DialogDangerButton {
                border: 1px solid #a83a46;
                border-radius: 12px;
                padding: 6px 18px;
                font-weight: 800;
                color: #fff4f4;
                background: #7a1f2b;
            }
            QPushButton#DialogDangerButton:hover, QPushButton#DialogDangerButton:focus {
                background: #912938;
                border: 1px solid #d05361;
            }
            QPushButton#DialogDangerButton:pressed { background: #5e1721; }
        """)


    def _register_focus_widget(self, widget: QtWidgets.QWidget) -> None:
        self._focus_widgets.append(widget)
        widget.installEventFilter(self)

    def _normalize_focus_order(self) -> None:
        widgets = []
        close_widgets = []
        initial = self._initial_focus_widget
        if initial is not None and initial in self._focus_widgets:
            widgets.append(initial)
        for widget in self._focus_widgets:
            if widget is initial:
                continue
            if widget.objectName() == "DialogCloseButton":
                close_widgets.append(widget)
            else:
                widgets.append(widget)
        self._focus_widgets = widgets + close_widgets
        chain = [self] + self._focus_widgets
        for first, second in zip(chain, chain[1:]):
            QtWidgets.QWidget.setTabOrder(first, second)

    def _focus_adjacent_widget(self, backward: bool = False) -> None:
        widgets = [widget for widget in self._focus_widgets if widget.isVisible() and widget.isEnabled()]
        if not widgets:
            self.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
            return
        focused = QtWidgets.QApplication.focusWidget()
        try:
            index = widgets.index(focused)
            next_index = (index - 1 if backward else index + 1) % len(widgets)
        except ValueError:
            if self._initial_focus_widget in widgets:
                next_index = widgets.index(self._initial_focus_widget)
            else:
                next_index = len(widgets) - 1 if backward else 0
        reason = QtCore.Qt.FocusReason.BacktabFocusReason if backward else QtCore.Qt.FocusReason.TabFocusReason
        widgets[next_index].setFocus(reason)

    def _focus_initial_widget(self) -> None:
        widget = self._initial_focus_widget
        if widget is not None and widget.isVisible() and widget.isEnabled():
            widget.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
            return
        self._focus_adjacent_widget(False)

    def _handle_modal_key(self, event: QtGui.QKeyEvent, target: Optional[QtCore.QObject] = None) -> bool:
        key = event.key()
        modifiers = event.modifiers()
        if key in (QtCore.Qt.Key.Key_Tab, QtCore.Qt.Key.Key_Backtab):
            self._focus_adjacent_widget(key == QtCore.Qt.Key.Key_Backtab or bool(modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier))
            event.accept()
            return True
        if key == QtCore.Qt.Key.Key_Escape:
            self.reject()
            return True
        if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            if isinstance(target, QtWidgets.QPushButton):
                return False
            focused = QtWidgets.QApplication.focusWidget()
            if isinstance(focused, QtWidgets.QPushButton) and focused in self._focus_widgets:
                focused.click()
                return True
            if self._initial_focus_widget is not None:
                self._initial_focus_widget.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
                if isinstance(self._initial_focus_widget, QtWidgets.QPushButton):
                    self._initial_focus_widget.click()
                    return True
            self.accept()
            return True
        return False

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        parent = self.parentWidget()
        if obj is parent and event.type() in (
            QtCore.QEvent.Type.Resize,
            QtCore.QEvent.Type.Move,
            QtCore.QEvent.Type.Show,
        ):
            self.setGeometry(parent.rect())
        if event.type() == QtCore.QEvent.Type.KeyPress and isinstance(event, QtGui.QKeyEvent):
            if obj in self._focus_widgets:
                if self._handle_modal_key(event, obj):
                    return True
            elif self._app_filter_installed and isinstance(obj, QtWidgets.QWidget):
                if obj is not self and not self.isAncestorOf(obj) and obj.window() is self.window():
                    if self._handle_modal_key(event, obj):
                        return True
                    return True
        return super().eventFilter(obj, event)


    def event(self, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.KeyPress and isinstance(event, QtGui.QKeyEvent):
            if self._handle_modal_key(event, self):
                return True
        return super().event(event)

    def focusNextPrevChild(self, next: bool) -> bool:
        self._focus_adjacent_widget(not next)
        return True

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if self.card.geometry().contains(event.position().toPoint()):
            super().mousePressEvent(event)
            return
        self.reject()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if self._handle_modal_key(event, self):
            return
        super().keyPressEvent(event)

    def _copy_message(self):
        QtWidgets.QApplication.clipboard().setText(self._copyable_error_detail())

    def _copy_link(self):
        if self._copy_link_url:
            QtWidgets.QApplication.clipboard().setText(self._copy_link_url)

    def _copyable_error_detail(self) -> str:
        text = str(self._message or "")
        markers = (
            "Подробности:",
            "Details:",
            "Details：",
            "详细信息：",
            "Detalles:",
            "Detalhes:",
            "Détails :",
            "詳細：",
            "세부 정보:",
        )
        for marker in markers:
            index = text.find(marker)
            if index >= 0:
                return text[index + len(marker):].strip()
        return text.strip()

    def _hide_open_popups(self):
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "_hide_open_popups"):
            parent._hide_open_popups()
        for widget in QtWidgets.QApplication.allWidgets():
            if widget.objectName() == "ComboPopup" and widget.isVisible():
                widget.hide()

    def _clear_parent_focus(self):
        parent = self.parentWidget()
        focused = QtWidgets.QApplication.focusWidget()
        if focused is not None and (parent is None or focused.window() is parent.window()):
            focused.clearFocus()
        if parent is not None:
            parent.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def _finish(self, result: int):
        self._result = result
        parent = self.parentWidget()
        if parent is not None:
            parent.removeEventFilter(self)
        if self._app_filter_installed:
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.removeEventFilter(self)
            self._app_filter_installed = False
        self._clear_parent_focus()
        self.hide()
        if self._loop is not None and self._loop.isRunning():
            self._loop.quit()
        QtCore.QTimer.singleShot(0, self._clear_parent_focus)
        self.deleteLater()

    def accept(self):
        self._finish(1)

    def reject(self):
        self._finish(0)

    def exec(self) -> int:
        self._hide_open_popups()
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        focused = QtWidgets.QApplication.focusWidget()
        if focused is not None:
            focused.clearFocus()
        app = QtWidgets.QApplication.instance()
        if app is not None and not self._app_filter_installed:
            app.installEventFilter(self)
            self._app_filter_installed = True
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
        self._loop = QtCore.QEventLoop(self)
        self._loop.exec()
        self._clear_parent_focus()
        return self._result

    @classmethod
    def information(cls, parent: Optional[QtWidgets.QWidget], title: str, message: str):
        return cls(parent, title, message, "info").exec()

    @classmethod
    def warning(cls, parent: Optional[QtWidgets.QWidget], title: str, message: str):
        return cls(parent, title, message, "warning").exec()

    @classmethod
    def critical(cls, parent: Optional[QtWidgets.QWidget], title: str, message: str, show_copy: bool = False):
        return cls(parent, title, message, "error", show_copy=show_copy).exec()

    @classmethod
    def confirm(
        cls,
        parent: Optional[QtWidgets.QWidget],
        title: str,
        message: str,
        ok_text: Optional[str] = None,
        cancel_text: Optional[str] = None,
        dangerous_ok: bool = False,
    ):
        return cls(parent, title, message, "warning", True, ok_text, cancel_text, dangerous_ok).exec()