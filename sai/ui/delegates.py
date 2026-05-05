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