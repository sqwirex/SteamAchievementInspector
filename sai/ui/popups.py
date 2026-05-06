from typing import Callable, Optional

from PyQt6 import QtCore, QtGui, QtWidgets


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
                padding-left: 0;
                padding-right: 0;
                padding-top: 0;
                padding-bottom: 3px;
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