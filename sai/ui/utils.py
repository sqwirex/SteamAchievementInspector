from PyQt6 import QtCore, QtGui, QtWidgets


def compact_elide(text: str, font_metrics: QtGui.QFontMetrics, width: int) -> str:
    if not text:
        return ""
    if width <= 0:
        return "..."
    if font_metrics.horizontalAdvance(text) <= width:
        return text
    ellipsis = "..."
    ellipsis_width = font_metrics.horizontalAdvance(ellipsis)
    if ellipsis_width >= width:
        return ellipsis
    trimmed = text.rstrip()
    while trimmed and font_metrics.horizontalAdvance(trimmed) + ellipsis_width > width:
        trimmed = trimmed[:-1].rstrip()
    return (trimmed or "") + ellipsis


def table_item_text_width(table: QtWidgets.QTableView, index: QtCore.QModelIndex) -> int:
    if not index.isValid():
        return 0
    rect = table.visualRect(index)
    col = index.column()
    if col == 0:
        return 0
    if col == 6:
        return max(0, rect.width() - 4)
    return max(0, rect.width() - 28)