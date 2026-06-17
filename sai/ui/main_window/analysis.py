from typing import Dict, List, Optional

from PyQt6 import QtCore

from sai.core.models import Achievement

class AnalysisMixin:

    def _base_items(self) -> List[Achievement]:
        items = self.achievements[:]
        appid = self.cmb_game.currentData()
        if appid:
            items = [a for a in items if a.appid == appid]
        return items

    def _achievement_display_name(self, a: Achievement) -> str:
        return a.name or a.apiname

    def _achievement_display_description(self, a: Achievement) -> str:
        return a.description or ""

    def _sort_items_for_view(self, items: List[Achievement]) -> List[Achievement]:
        asc = (self.cmb_sort.currentIndex() == 1)
        return sorted(items, key=lambda a: (a.unlock_time or 0, a.game_name, self._achievement_display_name(a)), reverse=not asc)

    def _filtered_sorted(self) -> List[Achievement]:
        items = self._base_items()
        ordered = self._sort_items_for_view(items)

        n_minutes = self.spin_n.value()
        exact_on = self.chk_only_exact.isChecked()
        susp_on  = self.chk_only_susp.isChecked()

        if exact_on and susp_on:
            within = self._filter_within_n(ordered, n_minutes)
            exact  = self._filter_exact_timestamp(ordered)
            want_ids = {id(x) for x in within} | {id(x) for x in exact}
            return [x for x in ordered if id(x) in want_ids]

        if exact_on:
            return self._filter_exact_timestamp(ordered)

        if susp_on:
            return self._filter_within_n(ordered, n_minutes)

        return ordered

    def _delta_map_ascending(self, items: List[Achievement]) -> Dict[int, Optional[int]]:
        chronological = sorted(items, key=lambda a: (a.unlock_time or 0, a.game_name, a.name))
        deltas: Dict[int, Optional[int]] = {}
        prev_ts: Optional[int] = None
        for a in chronological:
            if prev_ts is None or not a.unlock_time:
                deltas[id(a)] = None
            else:
                deltas[id(a)] = abs(a.unlock_time - prev_ts)
            if a.unlock_time:
                prev_ts = a.unlock_time
        return deltas

    def _analysis_signature_for_items(self, items: List[Achievement]) -> tuple:
        return tuple((id(a), int(a.unlock_time or 0)) for a in items)

    def _analysis_maps_for_items(self, items: List[Achievement]) -> tuple[Dict[int, Optional[int]], Dict[int, int]]:
        signature = self._analysis_signature_for_items(items)
        if signature == self._analysis_cache_signature:
            return self._analysis_cache_deltas, self._analysis_cache_exact_count

        delta_by_id = self._delta_map_ascending(items)
        exact_count: Dict[int, int] = {}
        for a in items:
            if a.unlock_time:
                exact_count[a.unlock_time] = exact_count.get(a.unlock_time, 0) + 1

        self._analysis_cache_signature = signature
        self._analysis_cache_deltas = delta_by_id
        self._analysis_cache_exact_count = exact_count
        return delta_by_id, exact_count

    def _filter_within_n(self, items: List[Achievement], n_minutes: int) -> List[Achievement]:
        if n_minutes <= 0 or len(items) < 2:
            return []
        n_sec = n_minutes * 60
        marked_ids = set()
        chronological = sorted(items, key=lambda a: (a.unlock_time or 0, a.game_name, a.name))
        for i in range(len(chronological) - 1):
            a, b = chronological[i], chronological[i + 1]
            if not (a.unlock_time and b.unlock_time):
                continue
            diff = abs(b.unlock_time - a.unlock_time)
            if 0 < diff <= n_sec:
                marked_ids.add(id(a))
                marked_ids.add(id(b))
        return [a for a in items if id(a) in marked_ids]

    def _filter_exact_timestamp(self, items: List[Achievement]) -> List[Achievement]:
        by_ts: Dict[int, List[int]] = {}
        for i, a in enumerate(items):
            if a.unlock_time:
                by_ts.setdefault(a.unlock_time, []).append(i)
        keep_idx = []
        for _, idxs in by_ts.items():
            if len(idxs) >= 2:
                keep_idx.extend(idxs)
        keep_idx = sorted(set(keep_idx))
        return [items[i] for i in keep_idx]

    def _format_delta_seconds(self, seconds: Optional[int], dash: Optional[str] = None) -> str:
        if seconds is None:
            return dash if dash is not None else self.i18n.t("dash")
        mins = seconds // 60
        secs = seconds % 60
        if mins > 0:
            return self.i18n.fmt("mins_secs_fmt", m=mins, s=secs)
        return self.i18n.fmt("secs_fmt", s=secs)

    def refresh_table(self, *args, update_status: bool = True):
        t = self.i18n
        items = self._filtered_sorted()
        self.table.setUpdatesEnabled(False)

        source_items = self._base_items()
        delta_by_id, exact_count = self._analysis_maps_for_items(source_items)

        n_sec_threshold = self.spin_n.value() * 60
        dash = t.t("dash")

        rows = []
        for a in items:
            icon_url = a.icon_url or ""
            icon = self.icon_cache.get(icon_url) if self.icons_enabled else None

            dt = a.unlock_dt()
            ts_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else dash

            d = delta_by_id.get(id(a))
            if d is None or not a.unlock_time:
                delta_str = dash
                delta_ok = False
            else:
                delta_str = self._format_delta_seconds(d, dash=dash)
                delta_ok = d <= max(1, n_sec_threshold)

            is_exact_dup = bool(a.unlock_time and exact_count.get(a.unlock_time, 0) >= 2)
            suspicious = is_exact_dup or (delta_str != dash and delta_ok)

            rows.append({
                "texts": [
                    "",
                    a.game_name,
                    self._achievement_display_name(a),
                    self._achievement_display_description(a),
                    ts_str,
                    delta_str,
                    "⚠" if suspicious else "",
                ],
                "icon_url": icon_url,
                "icon": icon,
                "suspicious": suspicious,
                "delta_bold": suspicious,
            })

        self.table_model.set_rows(rows)
        self._apply_compact_table_columns()
        self.table.setUpdatesEnabled(True)
        QtCore.QTimer.singleShot(0, self._refresh_table_geometry)
        self._schedule_visible_icon_load()

        if update_status and not self._export_blocked_until_ready:
            self._set_status("shown", n=self.table.rowCount())
        self._update_table_scroll_header()

    def reset_filters(self):
        view_changed = (
            self.cmb_sort.currentIndex() != 0
            or self.spin_n.value() != 2
        )
        filter_changed = (
            self.cmb_game.currentIndex() != 0
            or self.chk_only_susp.isChecked()
            or self.chk_only_exact.isChecked()
        )
        changed = view_changed or filter_changed

        controls = (
            self.cmb_game,
            self.cmb_sort,
            self.spin_n,
            self.chk_only_susp,
            self.chk_only_exact,
        )
        for control in controls:
            control.blockSignals(True)

        self.cmb_game.setCurrentIndex(0)
        self.cmb_sort.setCurrentIndex(0)
        self.spin_n.setValue(2)
        self.chk_only_susp.setChecked(False)
        self.chk_only_exact.setChecked(False)

        for control in controls:
            control.blockSignals(False)

        if changed:
            self.refresh_table(update_status=filter_changed)

    def _threshold_label(self) -> str:
        if self.chk_only_exact.isChecked():
            return self.i18n.t("thr_exact")
        n = self.spin_n.value()
        return self.i18n.fmt("thr_leq", n=n)