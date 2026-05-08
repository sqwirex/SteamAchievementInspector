from typing import Dict, List

from PyQt6 import QtCore, QtGui


class AchievementTableModel(QtCore.QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Dict] = []
        self._headers: List[str] = ["", "", "", "", "", "", ""]
        self._warn_color = QtGui.QColor("#f59f00")
        self._bold_font = QtGui.QFont()
        self._bold_font.setBold(True)

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else 7

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._rows) or col < 0 or col >= 7:
            return None

        item = self._rows[row]

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return ""
            if col == 6:
                return "⚠" if item.get("suspicious") else ""
            return item["texts"][col]

        if role == QtCore.Qt.ItemDataRole.DecorationRole and col == 0:
            return item.get("icon") or QtGui.QIcon()

        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            return int(QtCore.Qt.AlignmentFlag.AlignCenter)

        if role == QtCore.Qt.ItemDataRole.ForegroundRole and col == 6 and item.get("suspicious"):
            return QtGui.QBrush(self._warn_color)

        if role == QtCore.Qt.ItemDataRole.FontRole and col == 5 and item.get("delta_bold"):
            return self._bold_font

        if role == QtCore.Qt.ItemDataRole.UserRole and col == 0:
            return item.get("icon_url", "")

        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal and 0 <= section < len(self._headers):
            return self._headers[section]
        return None

    def flags(self, index: QtCore.QModelIndex):
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags
        return QtCore.Qt.ItemFlag.ItemIsEnabled

    def set_headers(self, headers: List[str]) -> None:
        self._headers = list(headers)
        if self.columnCount() > 0:
            self.headerDataChanged.emit(QtCore.Qt.Orientation.Horizontal, 0, self.columnCount() - 1)

    def set_rows(self, rows: List[Dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def clear(self) -> None:
        self.set_rows([])

    def icon_url_at(self, row: int) -> str:
        if 0 <= row < len(self._rows):
            return str(self._rows[row].get("icon_url") or "")
        return ""

    def set_icon_for_url(self, url: str, icon: QtGui.QIcon) -> List[int]:
        changed = []
        if not url:
            return changed
        for row, item in enumerate(self._rows):
            if item.get("icon_url") == url:
                item["icon"] = icon
                changed.append(row)
        for row in changed:
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [QtCore.Qt.ItemDataRole.DecorationRole])
        return changed