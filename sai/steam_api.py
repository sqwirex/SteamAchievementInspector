import re
import time
from typing import Dict, List, Optional

import requests

from .config import API_BASE, HEADERS


class InvalidAPIKeyError(PermissionError):
    pass


class SteamAPI:
    def __init__(self, api_key: str, lang: str = "en", timeout: int = 25):
        self.api_key = api_key
        self.lang = lang
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get(self, url: str, params: Dict) -> Dict:
        for attempt in range(3):
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (401, 403):
                    raise InvalidAPIKeyError(f"HTTP {r.status_code}")
                time.sleep(0.5 * (attempt + 1))
            except requests.RequestException:
                time.sleep(0.5 * (attempt + 1))
        r = self.session.get(url, params=params, timeout=self.timeout)
        if r.status_code in (401, 403):
            raise InvalidAPIKeyError(f"HTTP {r.status_code}")
        r.raise_for_status()
        return r.json()

    @staticmethod
    def looks_like_valid_key_format(key: str) -> bool:
        return bool(re.fullmatch(r"[A-Fa-f0-9]{32}", key))

    def resolve_steamid64(self, profile_url: str) -> str:
        u = profile_url.strip().rstrip("/")
        if re.fullmatch(r"\d{17}", u):
            return u
        m = re.search(r"/profiles/(\d{17})", u)
        if m:
            return m.group(1)
        vanity = None
        m = re.search(r"/id/([^/?#]+)", u)
        if m:
            vanity = m.group(1)
        elif re.fullmatch(r"[A-Za-z0-9_\-\.]+", u):
            vanity = u
        if vanity:
            url = f"{API_BASE}/ISteamUser/ResolveVanityURL/v0001/"
            data = self._get(url, {"key": self.api_key, "vanityurl": vanity})
            if data and data.get("response", {}).get("success") == 1:
                return data["response"]["steamid"]
            raise ValueError("Failed to resolve vanity to steamid64.")
        raise ValueError("Enter valid Steam profile URL or steamid64/vanity.")

    def verify_key_can_read_profile(self, steamid64: str) -> None:
        url = f"{API_BASE}/ISteamUser/GetPlayerSummaries/v0002/"
        _ = self._get(url, {"key": self.api_key, "steamids": steamid64})

    def get_player_achievements_full(self, steamid64: str, appid: int) -> List[Dict]:
        url = f"{API_BASE}/ISteamUserStats/GetPlayerAchievements/v0001/"
        params = {"key": self.api_key, "steamid": steamid64, "appid": appid, "l": self.lang}
        data = self._get(url, params)
        ps = data.get("playerstats", {})
        if ps.get("success") is False:
            return []
        achievements = ps.get("achievements", []) or []
        return [
            {"apiname": item.get("apiname", ""), "unlocktime": int(item.get("unlocktime", 0) or 0)}
            for item in achievements
            if bool(item.get("achieved", 0))
        ]

    def get_schema_for_game(self, appid: int, lang: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        url = f"{API_BASE}/ISteamUserStats/GetSchemaForGame/v2/"
        params = {"key": self.api_key, "appid": appid, "l": lang or self.lang}
        data = self._get(url, params)
        game = data.get("game", {})
        stats = game.get("availableGameStats", {}) or {}
        ach = stats.get("achievements", []) or []
        mapping: Dict[str, Dict[str, str]] = {}
        for a in ach:
            apiname = a.get("name", "")
            if not apiname:
                continue
            mapping[apiname] = {
                "displayName": a.get("displayName", apiname),
                "description": a.get("description", "") or "",
                "icon": a.get("icon", "") or "",
                "icongray": a.get("icongray", "") or "",
            }
        return mapping

    def get_owned_games(self, steamid64: str) -> List[Dict]:
        url = f"{API_BASE}/IPlayerService/GetOwnedGames/v0001/"
        params = {
            "key": self.api_key,
            "steamid": steamid64,
            "include_appinfo": 1,
            "include_played_free_games": 1,
            "format": "json",
        }
        data = self._get(url, params)
        games = data.get("response", {}).get("games", []) or []
        norm = []
        for g in games:
            appid = g.get("appid")
            name = g.get("name") or f"App {appid}"
            pt = int(g.get("playtime_forever") or 0)
            if appid:
                norm.append({"appid": appid, "name": name, "playtime": pt})
        norm.sort(key=lambda x: (-x["playtime"], x["name"].lower()))
        return norm