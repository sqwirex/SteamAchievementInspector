from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets


class CapsuleScrollBar(QtWidgets.QScrollBar):
    def __init__(self, orientation: QtCore.Qt.Orientation, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(orientation, parent)
        self._hover_handle = False
        self._reserved_start = 0
        self._dragging = False
        self._drag_offset = 0.0
        self.setMouseTracking(True)

        if orientation == QtCore.Qt.Orientation.Vertical:
            self.setFixedWidth(16)
        else:
            self.setFixedHeight(16)

        self.setStyleSheet("""
            QScrollBar {
                background: transparent;
                border: none;
            }
            QScrollBar::add-line,
            QScrollBar::sub-line,
            QScrollBar::add-page,
            QScrollBar::sub-page {
                width: 0px;
                height: 0px;
                background: transparent;
                border: none;
            }
        """)

    def set_reserved_start(self, value: int) -> None:
        value = max(0, int(value))
        if self._reserved_start != value:
            self._reserved_start = value
            self.update()

    def _is_vertical(self) -> bool:
        return self.orientation() == QtCore.Qt.Orientation.Vertical

    def _track_rect(self) -> QtCore.QRectF:
        rect = QtCore.QRectF(self.rect())

        if self._is_vertical():
            return rect.adjusted(4.6, self._reserved_start + 2, -3.4, -2)

        return rect.adjusted(2, 4.6, -2, -3.4)

    def _slider_rect(self) -> QtCore.QRectF:
        track = self._track_rect()
        vertical = self._is_vertical()

        track_len = max(1.0, track.height() if vertical else track.width())
        min_v = self.minimum()
        max_v = self.maximum()
        page = max(1, self.pageStep())
        span = max_v - min_v

        if span <= 0:
            ratio = 1.0
            pos_ratio = 0.0
        else:
            ratio = page / float(span + page)
            pos_ratio = (self.value() - min_v) / float(span)

        min_len = 40.0
        slider_len = max(min_len, track_len * ratio)
        slider_len = min(slider_len, track_len)
        slider_pos = (track_len - slider_len) * max(0.0, min(1.0, pos_ratio))

        if vertical:
            return QtCore.QRectF(track.x(), track.y() + slider_pos, track.width(), slider_len)
        return QtCore.QRectF(track.x() + slider_pos, track.y(), slider_len, track.height())

    def _event_axis_pos(self, event: QtGui.QMouseEvent) -> float:
        pos = event.position()
        return pos.y() if self._is_vertical() else pos.x()

    def _slider_axis_start(self) -> float:
        slider = self._slider_rect()
        return slider.y() if self._is_vertical() else slider.x()

    def _track_axis_start(self) -> float:
        track = self._track_rect()
        return track.y() if self._is_vertical() else track.x()

    def _track_axis_length(self) -> float:
        track = self._track_rect()
        return track.height() if self._is_vertical() else track.width()

    def _slider_axis_length(self) -> float:
        slider = self._slider_rect()
        return slider.height() if self._is_vertical() else slider.width()

    def _set_value_from_slider_axis_start(self, slider_start: float) -> None:
        min_v = self.minimum()
        max_v = self.maximum()
        span = max_v - min_v
        if span <= 0:
            return

        track_start = self._track_axis_start()
        movable_len = max(1.0, self._track_axis_length() - self._slider_axis_length())
        pos_ratio = (slider_start - track_start) / movable_len
        pos_ratio = max(0.0, min(1.0, pos_ratio))

        self.setValue(round(min_v + pos_ratio * span))

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        outline_pen = QtGui.QPen(QtGui.QColor("#2b3849"), 2)
        outline_pen.setCosmetic(True)
        painter.setPen(outline_pen)
        if self._is_vertical():
            painter.drawLine(0, 0, 0, self.height())
        else:
            painter.drawLine(0, 0, self.width(), 0)

        track = self._track_rect()
        if track.width() <= 0 or track.height() <= 0:
            return

        track_radius = min(track.width(), track.height()) / 2.0
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor("#101722"))
        painter.drawRoundedRect(track, track_radius, track_radius)

        if self.maximum() <= self.minimum():
            return

        handle = self._slider_rect()
        if handle.width() <= 0 or handle.height() <= 0:
            return

        handle_radius = min(handle.width(), handle.height()) / 2.0
        painter.setBrush(QtGui.QColor("#5f82aa") if (self._hover_handle or self._dragging) else QtGui.QColor("#4e7097"))
        painter.drawRoundedRect(handle, handle_radius, handle_radius)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        slider = self._slider_rect()
        axis_pos = self._event_axis_pos(event)

        if slider.contains(event.position()):
            self._dragging = True
            self._drag_offset = axis_pos - self._slider_axis_start()
            self.setSliderDown(True)
            self.grabMouse()
            event.accept()
            self.update()
            return

        if self._track_rect().contains(event.position()):
            self._dragging = True
            self._drag_offset = self._slider_axis_length() / 2.0
            self.setSliderDown(True)
            self.grabMouse()
            self._set_value_from_slider_axis_start(axis_pos - self._drag_offset)
            event.accept()
            self.update()
            return

        event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self._dragging:
            slider_start = self._event_axis_pos(event) - self._drag_offset
            self._set_value_from_slider_axis_start(slider_start)
            event.accept()
            self.update()
            return

        was_hover = self._hover_handle
        self._hover_handle = self._slider_rect().contains(event.position())
        if was_hover != self._hover_handle:
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if self._dragging and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setSliderDown(False)
            try:
                self.releaseMouse()
            except RuntimeError:
                pass
            event.accept()
            self.update()
            return

        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: QtCore.QEvent):
        if not self._dragging and self._hover_handle:
            self._hover_handle = False
            self.update()
        super().leaveEvent(event)