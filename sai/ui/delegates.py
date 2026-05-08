from PyQt6 import QtCore, QtGui, QtWidgets

from .utils import compact_elide


def centered_icon_rect(rect: QtCore.QRect, size: QtCore.QSize) -> QtCore.QRect:
    if not size.isValid() or size.width() <= 0 or size.height() <= 0:
        size = QtCore.QSize(34, 34)

    width = min(size.width(), max(0, rect.width()))
    height = min(size.height(), max(0, rect.height()))
    x = rect.x() + (rect.width() - width) // 2
    y = rect.y() + (rect.height() - height) // 2
    return QtCore.QRect(x, y, width, height)



def draw_warning_icon(
    painter: QtGui.QPainter,
    rect: QtCore.QRectF,
    *,
    icon_size: float = 13.0,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> None:
    painter.save()
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)

    cx = rect.center().x() + offset_x
    cy = rect.center().y() + offset_y
    half = icon_size / 2.0
    h = icon_size * 0.88

    top = QtCore.QPointF(cx, cy - h / 2.0)
    left = QtCore.QPointF(cx - half, cy + h / 2.0)
    right = QtCore.QPointF(cx + half, cy + h / 2.0)

    triangle = QtGui.QPainterPath()
    triangle.moveTo(top)
    triangle.lineTo(left)
    triangle.lineTo(right)
    triangle.closeSubpath()

    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtGui.QColor("#f59f00"))
    painter.drawPath(triangle)

    mark_color = QtGui.QColor("#111822")
    painter.setBrush(mark_color)

    bar_w = max(1.6, icon_size * 0.11)
    bar_h = icon_size * 0.34
    bar_rect = QtCore.QRectF(
        cx - bar_w / 2.0,
        cy - icon_size * 0.12,
        bar_w,
        bar_h,
    )
    painter.drawRoundedRect(bar_rect, 0.8, 0.8)

    dot_r = max(1.05, icon_size * 0.07)
    painter.drawEllipse(QtCore.QPointF(cx, cy + icon_size * 0.23), dot_r, dot_r)
    painter.restore()


class NoHighlightDelegate(QtWidgets.QStyledItemDelegate):

    def _draw_table_grid(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> None:
        table = option.widget
        if not isinstance(table, QtWidgets.QTableWidget):
            return

        painter.save()
        painter.setPen(QtGui.QPen(QtGui.QColor("#243142"), 1))

        rect = option.rect

        painter.drawLine(rect.left(), rect.bottom(), rect.right() + 1, rect.bottom())
        painter.restore()

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        State = getattr(QtWidgets.QStyle, "StateFlag", QtWidgets.QStyle)
        opt.state &= ~State.State_Selected
        opt.state &= ~State.State_MouseOver
        opt.state &= ~State.State_HasFocus

        style = opt.widget.style() if opt.widget else QtWidgets.QApplication.style()

        if index.column() == 0:
            icon = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
            opt.text = ""
            opt.icon = QtGui.QIcon()
            style.drawControl(QtWidgets.QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

            if isinstance(icon, QtGui.QIcon) and not icon.isNull():
                icon_rect = centered_icon_rect(opt.rect, opt.decorationSize)
                icon.paint(
                    painter,
                    icon_rect,
                    QtCore.Qt.AlignmentFlag.AlignCenter,
                    QtGui.QIcon.Mode.Normal,
                    QtGui.QIcon.State.Off,
                )
            self._draw_table_grid(painter, opt, index)
            return

        opt.text = ""
        style.drawControl(QtWidgets.QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        text = str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or "")

        if index.column() == 6:
            if text:
                draw_warning_icon(
                    painter,
                    QtCore.QRectF(opt.rect),
                    icon_size=13.0,
                )
            self._draw_table_grid(painter, opt, index)
            return

        alignment_data = index.data(QtCore.Qt.ItemDataRole.TextAlignmentRole)
        if alignment_data is None:
            alignment = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        else:
            alignment = QtCore.Qt.AlignmentFlag(int(alignment_data))
            if not (alignment & (QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignVCenter)):
                alignment |= QtCore.Qt.AlignmentFlag.AlignVCenter

        text_rect = opt.rect.adjusted(14, 0, -14, 0)
        shown = compact_elide(text, opt.fontMetrics, max(0, text_rect.width()))

        painter.save()
        painter.setFont(opt.font)
        painter.setPen(QtGui.QColor("#dce8f3"))
        painter.drawText(text_rect, int(alignment), shown)
        painter.restore()
        self._draw_table_grid(painter, opt, index)



class OffsetHeaderView(QtWidgets.QHeaderView):
    def _draw_centered_header_text(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRectF,
        text: str,
        color: QtGui.QColor,
        font: QtGui.QFont,
    ) -> None:
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(font)
        painter.setPen(color)

        fm = QtGui.QFontMetrics(font)
        br = fm.tightBoundingRect(text)
        x = rect.x() + (rect.width() - br.width()) / 2.0 - br.x()
        y = rect.y() + (rect.height() + br.height()) / 2.0 - br.bottom()
        painter.drawText(QtCore.QPointF(x, y), text)
        painter.restore()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)

        painter = QtGui.QPainter(self.viewport())
        painter.setPen(QtGui.QPen(QtGui.QColor("#2b3849"), 1))
        y = self.viewport().height() - 0.5
        painter.drawLine(QtCore.QPointF(-1.0, y), QtCore.QPointF(self.viewport().width() + 1.0, y))
        painter.end()

    def paintSection(self, painter: QtGui.QPainter, rect: QtCore.QRect, logicalIndex: int):
        if not rect.isValid():
            return

        opt = QtWidgets.QStyleOptionHeader()
        self.initStyleOption(opt)
        opt.rect = rect
        opt.section = logicalIndex
        opt.text = ""
        opt.position = QtWidgets.QStyleOptionHeader.SectionPosition.Middle
        if logicalIndex == 0:
            opt.position = QtWidgets.QStyleOptionHeader.SectionPosition.Beginning
        elif self.model() is not None and logicalIndex == self.model().columnCount() - 1:
            opt.position = QtWidgets.QStyleOptionHeader.SectionPosition.End

        painter.save()
        self.style().drawControl(QtWidgets.QStyle.ControlElement.CE_Header, opt, painter, self)
        painter.restore()

        header_text = self.model().headerData(
            logicalIndex,
            self.orientation(),
            QtCore.Qt.ItemDataRole.DisplayRole,
        ) if self.model() is not None else ""

        header_font = QtGui.QFont(self.font())
        header_font.setBold(True)
        header_font.setWeight(800)

        if logicalIndex == 6:
            draw_warning_icon(
                painter,
                QtCore.QRectF(rect),
                icon_size=12.5,
            )
        else:
            self._draw_centered_header_text(
                painter,
                QtCore.QRectF(rect),
                str(header_text or ""),
                QtGui.QColor("#a7bad0"),
                header_font,
            )


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