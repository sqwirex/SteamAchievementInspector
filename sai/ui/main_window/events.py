from contextlib import suppress
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from sai.ui.popups import ThemedMessageDialog

class EventsMixin:

    def _is_field_or_field_child(self, widget: Optional[QtWidgets.QWidget]) -> bool:
        while widget is not None:
            if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QComboBox, QtWidgets.QSpinBox)):
                return True
            widget = widget.parentWidget()
        return False

    def _clear_control_focus_on_background_click(self, obj: QtCore.QObject) -> None:
        if not isinstance(obj, QtWidgets.QWidget):
            return
        if obj.window() is not self:
            return
        if self._is_field_or_field_child(obj):
            return

        focused = QtWidgets.QApplication.focusWidget()
        if focused and focused.window() is self:
            focused.clearFocus()

    def _set_toggle_button_drag_outside(self, value: bool) -> None:
        if not hasattr(self, "btn_toggle_menu"):
            return
        if self.btn_toggle_menu.property("dragOutside") == value:
            return
        self.btn_toggle_menu.setProperty("dragOutside", value)
        self.btn_toggle_menu.style().unpolish(self.btn_toggle_menu)
        self.btn_toggle_menu.style().polish(self.btn_toggle_menu)
        self.btn_toggle_menu.update()

    def _reset_api_key_view_to_start(self) -> None:
        if not hasattr(self, "edt_key"):
            return
        if self.edt_key.hasSelectedText():
            return
        self.edt_key.setCursorPosition(0)

    def _confirm_api_key_reveal_from_enter(self) -> None:
        if not hasattr(self, "edt_key"):
            return
        result = ThemedMessageDialog.confirm(
            self,
            self.i18n.t("warning"),
            self.i18n.t("api_reveal_confirm"),
            self.i18n.t("reveal"),
            self.i18n.t("cancel"),
            dangerous_ok=True,
        )
        if result == 1:
            self.edt_key._toggle_secret_visibility()

    def _clear_keyboard_focus(self) -> None:
        focused = QtWidgets.QApplication.focusWidget()
        if focused and focused.window() is self:
            focused.clearFocus()
        self.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def _visible_combo_popup_owner(self) -> Optional[QtWidgets.QComboBox]:
        for combo in self.findChildren(QtWidgets.QComboBox):
            popup = getattr(combo, "_popup", None)
            if popup is not None and popup.isVisible():
                return combo
            view = combo.view()
            if view is not None and view.isVisible():
                return combo
        return None

    def _is_text_input_focus(self, widget: Optional[QtWidgets.QWidget]) -> bool:
        if isinstance(widget, QtWidgets.QLineEdit):
            return True
        if isinstance(widget, QtWidgets.QAbstractSpinBox):
            return True
        parent = widget.parentWidget() if isinstance(widget, QtWidgets.QWidget) else None
        while parent is not None:
            if isinstance(parent, QtWidgets.QAbstractSpinBox):
                return True
            parent = parent.parentWidget()
        return False

    def _scroll_table_with_arrows(self, key: int) -> bool:
        if not hasattr(self, "table"):
            return False
        if self._is_text_input_focus(QtWidgets.QApplication.focusWidget()):
            return False
        if key in (QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_Right):
            bar = self.table.horizontalScrollBar()
            direction = -1 if key == QtCore.Qt.Key.Key_Left else 1
        elif key in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down):
            bar = self.table.verticalScrollBar()
            direction = -1 if key == QtCore.Qt.Key.Key_Up else 1
        else:
            return False
        step = bar.singleStep() or 40
        bar.setValue(bar.value() + direction * step)
        return True

    def _handle_global_key_press(self, event: QtGui.QKeyEvent) -> bool:
        key = event.key()
        focused = QtWidgets.QApplication.focusWidget()
        popup_owner = self._visible_combo_popup_owner()
        if key == QtCore.Qt.Key.Key_Escape:
            if popup_owner is not None:
                popup_owner.hidePopup()
            elif isinstance(focused, QtWidgets.QComboBox):
                focused.hidePopup()
            self._clear_keyboard_focus()
            event.accept()
            return True
        if popup_owner is not None:
            handler = getattr(popup_owner, "_handle_popup_key", None)
            if handler is not None and handler(event):
                return True
        if popup_owner is None and self._scroll_table_with_arrows(key):
            event.accept()
            return True
        if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            if isinstance(focused, QtWidgets.QCheckBox) and focused.isEnabled():
                focused.toggle()
                event.accept()
                return True
            if isinstance(focused, QtWidgets.QComboBox):
                popup = getattr(focused, "_popup", None)
                if popup is not None and popup.isVisible():
                    return False
                focused.showPopup()
                event.accept()
                return True
            if isinstance(focused, (QtWidgets.QPushButton, QtWidgets.QToolButton)) and focused.isEnabled():
                focused.click()
                event.accept()
                return True
        return False

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.KeyPress and isinstance(event, QtGui.QKeyEvent):
            if self._handle_global_key_press(event):
                return True

        if hasattr(self, "edt_key") and obj is self.edt_key:
            event_type = event.type()
            if event_type in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.FocusOut):
                if not getattr(self.edt_key, "_suppress_view_reset", False):
                    QtCore.QTimer.singleShot(0, self._reset_api_key_view_to_start)

        if hasattr(self, "btn_toggle_menu") and obj is self.btn_toggle_menu:
            event_type = event.type()
            if event_type == QtCore.QEvent.Type.MouseButtonPress:
                self._toggle_button_pressed = True
                self._set_toggle_button_drag_outside(False)
            elif event_type == QtCore.QEvent.Type.MouseMove and self._toggle_button_pressed:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                self._set_toggle_button_drag_outside(not self.btn_toggle_menu.rect().contains(pos))
            elif event_type in (QtCore.QEvent.Type.Leave, QtCore.QEvent.Type.HoverLeave) and self._toggle_button_pressed:
                self._set_toggle_button_drag_outside(True)
            elif event_type == QtCore.QEvent.Type.MouseButtonRelease:
                self._toggle_button_pressed = False
                QtCore.QTimer.singleShot(0, lambda: self._set_toggle_button_drag_outside(False))

        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            self._clear_control_focus_on_background_click(obj)

        if hasattr(self, "table") and obj is self.table.viewport():
            if event.type() in (
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QEvent.Type.MouseButtonRelease,
                QtCore.QEvent.Type.MouseButtonDblClick,
            ):
                return True
        return super().eventFilter(obj, event)

    def _refresh_table_geometry(self):
        self._apply_compact_table_columns()
        self._update_table_scroll_header()
        self.table.viewport().update()
        self.table.horizontalHeader().viewport().update()
        self._schedule_visible_icon_load()

    def showEvent(self, event: QtGui.QShowEvent):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._refresh_table_geometry)
        QtCore.QTimer.singleShot(50, self._refresh_table_geometry)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._refresh_table_geometry)

    def toggle_controls_menu(self):
        if not hasattr(self, "controls_card") or not hasattr(self, "btn_toggle_menu"):
            return
        if self._menu_animating:
            return

        focused = QtWidgets.QApplication.focusWidget()
        keep_toggle_focus = focused is self.btn_toggle_menu
        if focused and focused.window() is self and not keep_toggle_focus:
            focused.clearFocus()

        self._menu_animating = True
        self.btn_toggle_menu.setEnabled(False)
        self.controls_card.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        if self._menu_animation_group is not None:
            with suppress(RuntimeError):
                if self._menu_animation_group.state() == QtCore.QAbstractAnimation.State.Running:
                    self._menu_animation_group.stop()
                self._menu_animation_group.deleteLater()
            self._menu_animation_group = None

        expanded_height = max(self.controls_card.sizeHint().height(), self.controls_card.layout().sizeHint().height())
        end_collapsed = not self._menu_collapsed

        if end_collapsed:
            start_height = max(self.controls_card.height(), expanded_height)
            end_height = 0
            start_opacity = 1.0
            end_opacity = 0.0
        else:
            self.controls_card.show()
            self.controls_card.setMaximumHeight(0)
            start_height = 0
            end_height = expanded_height
            start_opacity = 0.0
            end_opacity = 1.0

        opacity_effect = self.controls_card.graphicsEffect()
        if not isinstance(opacity_effect, QtWidgets.QGraphicsOpacityEffect):
            opacity_effect = QtWidgets.QGraphicsOpacityEffect(self.controls_card)
            self.controls_card.setGraphicsEffect(opacity_effect)
        opacity_effect.setOpacity(start_opacity)

        height_anim = QtCore.QPropertyAnimation(self.controls_card, b"maximumHeight", self)
        height_anim.setDuration(220)
        height_anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutCubic)
        height_anim.setStartValue(start_height)
        height_anim.setEndValue(end_height)

        opacity_anim = QtCore.QPropertyAnimation(opacity_effect, b"opacity", self)
        opacity_anim.setDuration(180)
        opacity_anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutQuad)
        opacity_anim.setStartValue(start_opacity)
        opacity_anim.setEndValue(end_opacity)

        group = QtCore.QParallelAnimationGroup(self)
        group.addAnimation(height_anim)
        group.addAnimation(opacity_anim)

        def finalize():
            self._menu_collapsed = end_collapsed
            if self._menu_collapsed:
                self.controls_card.setMaximumHeight(0)
                self.controls_card.hide()
                self.btn_toggle_menu.setArrowType(QtCore.Qt.ArrowType.DownArrow)
            else:
                self.controls_card.show()
                self.controls_card.setMaximumHeight(16777215)
                opacity_effect.setOpacity(1.0)
                self.btn_toggle_menu.setArrowType(QtCore.Qt.ArrowType.UpArrow)
            self.controls_card.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.btn_toggle_menu.setEnabled(True)
            if end_collapsed:
                if keep_toggle_focus:
                    QtCore.QTimer.singleShot(0, self.btn_toggle_menu.setFocus)
                else:
                    QtCore.QTimer.singleShot(0, self._clear_keyboard_focus)
            self._menu_animating = False
            self._menu_animation_group = None
            group.deleteLater()

        group.finished.connect(finalize)
        self._menu_animation_group = group
        group.start()

    def _apply_compact_table_columns(self):
        if not hasattr(self, "table"):
            return

        for col in range(7):
            self.table.setColumnHidden(col, False)

        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)

        base_widths = [70, 220, 260, 380, 170, 90, 46]
        for col, width in enumerate(base_widths):
            if col in (0, 6):
                hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Fixed)
            elif col != 3:
                hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, width)

        viewport_width = self.table.viewport().width()
        total_base = sum(base_widths)
        vbar = self.table.verticalScrollBar()
        has_vertical_scroll = self.table.rowCount() > 0 and vbar.maximum() > 0
        desired_policy = (
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if has_vertical_scroll
            else QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        if self.table.verticalScrollBarPolicy() != desired_policy:
            self.table.setVerticalScrollBarPolicy(desired_policy)
            viewport_width = self.table.viewport().width()

        if viewport_width >= total_base:
            hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(3, base_widths[3] + (viewport_width - total_base))
        else:
            hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(3, base_widths[3])

    def _update_table_scroll_header(self):
        if not hasattr(self, "table_scroll_header"):
            return

        sb = self.table.verticalScrollBar()
        header = self.table.horizontalHeader()
        if header.width() <= 0 or self.table.viewport().width() <= 0:
            self.table_scroll_header.hide()
            return
        if not sb.isVisible() or sb.maximum() <= 0:
            if hasattr(sb, "set_reserved_start"):
                sb.set_reserved_start(0)
            self.table_scroll_header.hide()
            return

        sb_geo = sb.geometry()
        hdr_geo = header.geometry()

        if hasattr(sb, "set_reserved_start"):
            sb.set_reserved_start(hdr_geo.height() + 1)
        x = max(0, self.table.width() - sb_geo.width() + 1)
        y = hdr_geo.y()
        w = sb_geo.width() + 2
        h = hdr_geo.height()
        self.table_scroll_header.setGeometry(x, y, w, h)
        self.table_scroll_header.show()
        self.table_scroll_header.raise_()
        self.table_scroll_header.update()

    def _clear_input_selection_after_dialog(self, focus_widget: Optional[QtWidgets.QWidget] = None):
        for line_edit in self.findChildren(QtWidgets.QLineEdit):
            line_edit.deselect()
            line_edit.clearFocus()
        if focus_widget is not None:
            focus_widget.clearFocus()
        focused = QtWidgets.QApplication.focusWidget()
        if focused and focused.window() is self:
            focused.clearFocus()
        self.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
        QtCore.QTimer.singleShot(0, self._clear_keyboard_focus)