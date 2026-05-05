import threading
from typing import Dict, List

from PyQt6 import QtCore

from .i18n import I18n
from .models import Achievement
from .steam_api import InvalidAPIKeyError, SteamAPI


class ListGamesWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
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
            api = SteamAPI(self.api_key, self.lang)
            steamid64 = api.resolve_steamid64(self.profile_url)
            api.verify_key_can_read_profile(steamid64)
            games = api.get_owned_games(steamid64)
            self.signals.finished.emit(steamid64, games)
        except InvalidAPIKeyError:
            i18n = I18n(self.lang)
            self.signals.error.emit(i18n.t("api_invalid"))
        except Exception as e:
            self.signals.error.emit(str(e))


class GameFetchWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        partial = QtCore.pyqtSignal(list)
        done = QtCore.pyqtSignal()
        error = QtCore.pyqtSignal(str)

    def __init__(self, api_key: str, lang: str, steamid64: str, game: Dict, cancel_event: threading.Event):
        super().__init__()
        self.api_key = api_key
        self.lang = lang
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
            api = SteamAPI(self.api_key, self.lang)
            appid = int(self.game["appid"])
            gname = self.game["name"]

            pa = api.get_player_achievements_full(self.steamid64, appid)
            achs: List[Achievement] = []
            if pa:
                if self.cancel_event.is_set():
                    return
                try:
                    schema = api.get_schema_for_game(appid, "en")
                except Exception:
                    schema = {}

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
