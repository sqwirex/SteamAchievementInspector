from contextlib import suppress
from typing import Optional, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets

from .delegates import ComboItemDelegate
from .popups import CellPreviewPopup, CustomTextContextMenu
from .utils import compact_elide, table_item_text_width


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

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        self._erase_trailing_gridline()

    def _erase_trailing_gridline(self) -> None:
        scrollbar = self.verticalScrollBar()
        if not scrollbar.isVisible() or self.columnCount() <= 0:
            return

        last_col = self.columnCount() - 1
        x = self.columnViewportPosition(last_col) + self.columnWidth(last_col) - 1
        viewport = self.viewport()
        if x < 0 or x >= viewport.width():
            return

        painter = QtGui.QPainter(viewport)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)

        base_color = QtGui.QColor('#111822')
        alt_color = QtGui.QColor('#141d29')

        visible_bottom = viewport.height()

        for row in range(self.rowCount()):
            y = self.rowViewportPosition(row)
            h = self.rowHeight(row)
            if y + h <= 0:
                continue
            if y >= visible_bottom:
                break

            top = max(y, 0)
            bottom = min(y + h, visible_bottom)
            height = bottom - top
            if height <= 1:
                continue

            painter.setBrush(alt_color if (self.alternatingRowColors() and row % 2 == 1) else base_color)
            painter.drawRect(x, top, 1, height - 1)

    def _clear_current(self):
        with suppress(Exception):
            self.selectionModel().clearSelection()
        self.setCurrentIndex(QtCore.QModelIndex())
        self.clearFocus()


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
                self.clearFocus()
                event.accept()
                return
            if down_rect.contains(pos):
                self.stepDown()
                self.clearFocus()
                event.accept()
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        self._context_menu_popup = CustomTextContextMenu(self.lineEdit())
        self._context_menu_popup.popup(event.globalPos())
        event.accept()


class CustomComboPopup(QtWidgets.QWidget):
    itemClicked = QtCore.pyqtSignal(int)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        parent = self.parent()
        if hasattr(parent, "_popup_hidden_at"):
            parent._popup_hidden_at = QtCore.QDateTime.currentMSecsSinceEpoch()
        super().hideEvent(event)

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
    POPUP_REOPEN_GUARD_MS = 50

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._popup_hidden_at = 0
        self._popup = CustomComboPopup(self)
        self._popup.itemClicked.connect(self._apply_popup_index)

    def _apply_popup_index(self, row: int):
        if 0 <= row < self.count():
            self.setCurrentIndex(row)
        self.clearFocus()

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
        now = QtCore.QDateTime.currentMSecsSinceEpoch()
        if now - self._popup_hidden_at < self.POPUP_REOPEN_GUARD_MS:
            return

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