import csv
import os
from datetime import datetime

from PyQt6 import QtWidgets

from sai.core.paths import app_exports_dir
from sai.ui.popups import ThemedMessageDialog

class ExportMixin:

    def _csv_text(self, value: str) -> str:
        text = str(value or "")
        replacements = {
            "≤": "<=",
            "Δ": "Delta",
            "⚠": "!",
            "—": "-",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def _csv_delta_text(self, value: str) -> str:
        return self._csv_text(value)

    def _csv_filename_identifier(self) -> str:
        profile = (self.current_profile_url or self.edt_profile.text() or "").strip().rstrip("/")
        identifier = ""

        if "/id/" in profile:
            identifier = profile.split("/id/", 1)[1].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
        elif profile and "/profiles/" not in profile and not profile.isdigit():
            identifier = profile.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]

        if not identifier:
            identifier = self.current_steamid or profile or "profile"

        safe = []
        for ch in identifier:
            if ch.isalnum() or ch in ("-", "_", "."):
                safe.append(ch)
            else:
                safe.append("_")
        cleaned = "".join(safe).strip("._-")
        return cleaned or "profile"

    def _csv_default_filename(self) -> str:
        localized_names = {
            "ru": "достижения",
            "zh_CN": "成就",
            "es": "logros",
            "pt_BR": "conquistas",
            "de": "erfolge",
            "fr": "succes",
            "ja": "実績",
            "ko": "도전과제",
        }
        base_name = localized_names.get(self.i18n.lang, "achievements")
        return f"{base_name}_{self._csv_filename_identifier()}.csv"

    def export_csv(self):
        t = self.i18n.t
        if self._export_blocked_until_ready:
            ThemedMessageDialog.warning(self, t("warning"), t("export_loading"))
            self._clear_input_selection_after_dialog(self.btn_export)
            return
        if self.table.rowCount() == 0:
            ThemedMessageDialog.information(self, t("info"), t("export_none"))
            self._clear_input_selection_after_dialog(self.btn_export)
            return

        default_path = os.path.join(app_exports_dir(), self._csv_default_filename())
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("save_csv"),
                                                        default_path, "CSV (*.csv)")
        if not path:
            self._clear_input_selection_after_dialog()
            return

        exported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game_filter = self.cmb_game.currentText() or t("all_games")
        sort_label = self.cmb_sort.currentText()
        threshold_text = self._threshold_label()
        only_susp = t("toggle_on") if self.chk_only_susp.isChecked() else t("toggle_off")
        only_exact = t("toggle_on") if self.chk_only_exact.isChecked() else t("toggle_off")

        def write_csv(to_path: str):
            items = self._filtered_sorted()
            source_items = self._base_items()
            delta_by_id, exact_count = self._analysis_maps_for_items(source_items)

            n_sec_threshold = self.spin_n.value() * 60
            dash = t("dash")

            with open(to_path, "w", newline="", encoding="utf-16", errors="strict") as f:
                export_title = t("export_title")
                exported_label = t("exported")
                profile_label = t("profile")
                ui_language_label = t("ui_language")
                game_filter_label = t("game_filter")
                sort_label_name = t("sort_label")
                threshold_label = t("threshold")
                only_suspicious_label = t("only_suspicious_filter")
                only_exact_label = t("only_exact_filter")

                f.write(f"# {self._csv_text(export_title)}\n")
                f.write(f"# {self._csv_text(exported_label)}: {self._csv_text(exported_at)}\n")
                f.write(f"# {self._csv_text(profile_label)}: {self._csv_text(self.current_profile_url)}\n")
                f.write(f"# {self._csv_text(ui_language_label)}: {self._csv_text(self.i18n.lang)}\n")
                f.write(f"# {self._csv_text(game_filter_label)}: {self._csv_text(game_filter)}\n")
                f.write(f"# {self._csv_text(sort_label_name)}: {self._csv_text(sort_label)}\n")
                f.write(f"# {self._csv_text(threshold_label)}: {self._csv_text(threshold_text)}\n")
                f.write(f"# {self._csv_text(only_suspicious_label)}: {self._csv_text(only_susp)}\n")
                f.write(f"# {self._csv_text(only_exact_label)}: {self._csv_text(only_exact)}\n")

                w = csv.writer(f, delimiter="\t", lineterminator="\n")
                w.writerow([
                    self._csv_text(t("hdr_game")),
                    self._csv_text(t("hdr_ach")),
                    self._csv_text(t("hdr_desc")),
                    self._csv_text(t("hdr_time")),
                    self._csv_text(t("export_hdr_delta")),
                    self._csv_text(t("hdr_suspicious")),
                ])

                for a in items:
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

                    w.writerow([
                        self._csv_text(a.game_name),
                        self._csv_text(self._achievement_display_name(a)),
                        self._csv_text(self._achievement_display_description(a)),
                        self._csv_text(ts_str),
                        self._csv_delta_text(delta_str),
                        self._csv_text(t("susp_yes")) if suspicious else "",
                    ])

        try:
            write_csv(path)
        except PermissionError:
            base, ext = os.path.splitext(path)
            alt = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext or '.csv'}"
            ThemedMessageDialog.warning(
                self, self.i18n.t("error"),
                self.i18n.t("export_permission_denied")
            )
            new_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("save_csv"), alt, "CSV (*.csv)")
            if new_path:
                write_csv(new_path)
            else:
                self._clear_input_selection_after_dialog()
                return

        ThemedMessageDialog.information(self, t("info"), t("export_done"))
        self._clear_input_selection_after_dialog()