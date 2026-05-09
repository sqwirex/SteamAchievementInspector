import threading
from typing import Dict, List

from PyQt6 import QtCore

from sai.core.i18n import I18n
from sai.core.models import Achievement
from sai.storage.cache import read_schema, read_schema_any, write_schema
from sai.services.steam_api import InvalidAPIKeyError, SteamAPI


SCHEMA_STALE_REFRESH_LIMIT = 50
_schema_refresh_lock = threading.Lock()
_schema_stale_refreshes = 0


def _reserve_stale_schema_refresh() -> bool:
    global _schema_stale_refreshes
    with _schema_refresh_lock:
        if _schema_stale_refreshes >= SCHEMA_STALE_REFRESH_LIMIT:
            return False
        _schema_stale_refreshes += 1
        return True


class ListGamesWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        loading_games = QtCore.pyqtSignal()
        finished = QtCore.pyqtSignal(str, list)
        error = QtCore.pyqtSignal(str)

    def __init__(self, api_key: str, profile_url: str, lang: str):
        super().__init__()
        self.api_key = api_key
        self.profile_url = profile_url
        self.lang = lang
        self.signals = ListGamesWorker.Signals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            api = SteamAPI(self.api_key)
            steamid64 = api.resolve_steamid64(self.profile_url)
            api.verify_key_can_read_profile(steamid64)
            self.signals.loading_games.emit()
            games = api.get_owned_games(steamid64)
            self.signals.finished.emit(steamid64, games)
        except InvalidAPIKeyError:
            i18n = I18n(self.lang)
            self.signals.error.emit(i18n.t("api_invalid"))
        except ValueError as e:
            i18n = I18n(self.lang)
            key = str(e)
            self.signals.error.emit(i18n.t(key) if key in ("invalid_profile", "vanity_failed") else key)
        except Exception as e:
            self.signals.error.emit(str(e))


class GameFetchWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        partial = QtCore.pyqtSignal(list)
        done = QtCore.pyqtSignal()
        error = QtCore.pyqtSignal(str)

    def __init__(self, api_key: str, steamid64: str, game: Dict, cancel_event: threading.Event):
        super().__init__()
        self.api_key = api_key
        self.steamid64 = steamid64
        self.game = game
        self.cancel_event = cancel_event
        self.signals = GameFetchWorker.Signals()

    @QtCore.pyqtSlot()
    def run(self):
        if self.cancel_event.is_set():
            self.signals.done.emit()
            return
        try:
            api = SteamAPI(self.api_key)
            appid = int(self.game["appid"])
            gname = self.game["name"]

            pa = api.get_player_achievements_full(self.steamid64, appid)
            achs: List[Achievement] = []
            if pa:
                schema = read_schema(appid)
                if schema is None:
                    stale_schema = read_schema_any(appid)
                    should_refresh = stale_schema is None or _reserve_stale_schema_refresh()
                    if should_refresh:
                        try:
                            schema = api.get_schema_for_game(appid)
                            write_schema(appid, schema)
                        except Exception:
                            schema = stale_schema or {}
                    else:
                        schema = stale_schema or {}

                for a in pa:
                    apiname = a["apiname"]
                    meta = schema.get(apiname, {})
                    achs.append(
                        Achievement(
                            appid=appid,
                            game_name=gname,
                            apiname=apiname,
                            name=(meta.get("displayName") or apiname),
                            description=(meta.get("description") or ""),
                            icon_url=(meta.get("icon") or ""),
                            unlock_time=int(a["unlocktime"]),
                        )
                    )
                self.signals.partial.emit(achs)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.done.emit()