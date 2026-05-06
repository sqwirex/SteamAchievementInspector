from PyQt6 import QtCore, QtGui, QtWidgets

from .utils import compact_elide


class NoHighlightDelegate(QtWidgets.QStyledItemDelegate):
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
                icon_size = opt.decorationSize
                if not icon_size.isValid() or icon_size.width() <= 0 or icon_size.height() <= 0:
                    icon_size = QtCore.QSize(34, 34)

                pix = icon.pixmap(icon_size)
                x = opt.rect.x() + (opt.rect.width() - pix.width()) / 2.0 + 4.75
                y = opt.rect.y() + (opt.rect.height() - pix.height()) / 2.0 + 5.0
                painter.drawPixmap(QtCore.QPointF(x, y), pix)
            return

        opt.text = ""
        style.drawControl(QtWidgets.QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        text = str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or "")

        if index.column() == 6:
            if text:
                painter.save()

                warning_font = QtGui.QFont(opt.font)
                warning_font.setBold(True)
                warning_font.setWeight(800)

                painter.setFont(warning_font)
                painter.setPen(QtGui.QColor("#f59f00"))

                fm = QtGui.QFontMetrics(warning_font)
                br = fm.tightBoundingRect(text)

                x = opt.rect.x() + (opt.rect.width() - br.width()) / 2.0 - br.x() + 1.5
                y = opt.rect.y() + (opt.rect.height() + br.height()) / 2.0 - br.bottom()

                painter.drawText(QtCore.QPointF(x, y), text)
                painter.restore()
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
            extra_x = 0.5
            table = self.parentWidget()
            if isinstance(table, QtWidgets.QAbstractItemView):
                vbar = table.verticalScrollBar()
                if not vbar.isVisible() or vbar.maximum() <= 0:
                    extra_x += 0.5

            self._draw_centered_header_text(
                painter,
                QtCore.QRectF(rect).translated(extra_x, -0.5),
                "⚠",
                QtGui.QColor("#f59f00"),
                header_font,
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