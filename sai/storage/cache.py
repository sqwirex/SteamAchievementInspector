import hashlib
import json
import os
import shutil
import tempfile
import time
from typing import Dict, Iterable, List, Optional

from sai.core.models import Achievement
from sai.core.paths import app_cache_dir

SCHEMA_MAX_AGE_DAYS = 30
ICON_MAX_AGE_DAYS = 180
USER_MAX_AGE_DAYS = 90
MAX_ICON_CACHE_MB = 300


def _ensure_dir(*parts: str) -> str:
    path = os.path.join(app_cache_dir(), *parts)
    os.makedirs(path, exist_ok=True)
    return path


def _atomic_write_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _atomic_write_json(path: str, payload: object) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    _atomic_write_bytes(path, data)


def _hash_text(value: str) -> str:
    return hashlib.sha1(str(value or "").encode("utf-8", errors="ignore")).hexdigest()


def _is_fresh(path: str, max_age_days: int) -> bool:
    if max_age_days <= 0:
        return True
    try:
        age_seconds = time.time() - os.path.getmtime(path)
    except OSError:
        return False
    return age_seconds <= max_age_days * 24 * 60 * 60


def icon_cache_path(url: str) -> str:
    return os.path.join(_ensure_dir("icons"), f"{_hash_text(url)}.img")


def read_icon_bytes(url: str) -> Optional[bytes]:
    path = icon_cache_path(url)
    try:
        if os.path.isfile(path) and os.path.getsize(path) > 0 and _is_fresh(path, ICON_MAX_AGE_DAYS):
            with open(path, "rb") as f:
                return f.read()
    except OSError:
        return None
    return None


def write_icon_bytes(url: str, data: bytes) -> None:
    if not url or not data:
        return
    _atomic_write_bytes(icon_cache_path(url), data)


def schema_cache_path(appid: int) -> str:
    safe = int(appid)
    return os.path.join(_ensure_dir("schemas"), f"{safe}.json")


def read_schema(appid: int, max_age_days: int = SCHEMA_MAX_AGE_DAYS) -> Optional[Dict[str, Dict[str, str]]]:
    path = schema_cache_path(appid)
    try:
        if not _is_fresh(path, max_age_days):
            return None
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            if isinstance(payload.get("achievements"), dict):
                return payload["achievements"]
            return payload
    except (OSError, ValueError, TypeError):
        return None
    return None


def is_schema_fresh(appid: int, max_age_days: int = SCHEMA_MAX_AGE_DAYS) -> bool:
    path = schema_cache_path(appid)
    return os.path.isfile(path) and _is_fresh(path, max_age_days)


def read_schema_any(appid: int) -> Optional[Dict[str, Dict[str, str]]]:
    return read_schema(appid, max_age_days=0)


def write_schema(appid: int, schema: Dict[str, Dict[str, str]]) -> None:
    if not schema:
        return
    payload = {"appid": int(appid), "cached_at": int(time.time()), "achievements": schema}
    _atomic_write_json(schema_cache_path(appid), payload)


def user_cache_path(steamid64: str) -> str:
    safe = "".join(ch for ch in str(steamid64 or "") if ch.isdigit()) or "unknown"
    return os.path.join(_ensure_dir("users"), safe, "achievements.json")


def read_user_achievements(steamid64: str) -> List[Achievement]:
    path = user_cache_path(steamid64)
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        rows = payload.get("achievements", []) if isinstance(payload, dict) else []
    except (OSError, ValueError, TypeError):
        return []

    achievements: List[Achievement] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            appid = int(row.get("appid") or 0)
            unlock_time = int(row.get("unlock_time") or 0)
        except (TypeError, ValueError):
            continue
        apiname = str(row.get("apiname") or "").strip()
        if not appid or not apiname:
            continue
        achievements.append(
            Achievement(
                appid=appid,
                game_name=str(row.get("game_name") or f"App {appid}"),
                apiname=apiname,
                name=str(row.get("name") or apiname),
                description=str(row.get("description") or ""),
                icon_url=str(row.get("icon_url") or ""),
                unlock_time=unlock_time,
            )
        )
    return achievements


def write_user_achievements(steamid64: str, achievements: Iterable[Achievement]) -> None:
    if not steamid64:
        return
    rows = []
    seen = set()
    for a in achievements:
        key = (int(a.appid or 0), str(a.apiname or ""), int(a.unlock_time or 0))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        rows.append({
            "appid": int(a.appid or 0),
            "game_name": a.game_name or f"App {a.appid}",
            "apiname": a.apiname or "",
            "name": a.name or a.apiname or "",
            "description": a.description or "",
            "icon_url": a.icon_url or "",
            "unlock_time": int(a.unlock_time or 0),
        })
    payload = {"steamid64": str(steamid64), "cached_at": int(time.time()), "achievements": rows}
    _atomic_write_json(user_cache_path(steamid64), payload)


def _remove_if_old(path: str, max_age_days: int) -> None:
    if not _is_fresh(path, max_age_days):
        try:
            os.remove(path)
        except OSError:
            pass


def _prune_icon_cache_by_size(max_mb: int) -> None:
    icons_dir = os.path.join(app_cache_dir(), "icons")
    if not os.path.isdir(icons_dir):
        return
    files = []
    total = 0
    for name in os.listdir(icons_dir):
        path = os.path.join(icons_dir, name)
        try:
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path)
            total += size
            files.append((os.path.getmtime(path), size, path))
        except OSError:
            continue
    limit = max(1, int(max_mb)) * 1024 * 1024
    if total <= limit:
        return
    for _, size, path in sorted(files):
        try:
            os.remove(path)
            total -= size
        except OSError:
            pass
        if total <= limit:
            break



def cache_size_bytes() -> int:
    base = app_cache_dir()
    total = 0
    if not os.path.isdir(base):
        return 0
    for root, _, files in os.walk(base):
        for name in files:
            path = os.path.join(root, name)
            try:
                if os.path.isfile(path):
                    total += os.path.getsize(path)
            except OSError:
                continue
    return total


def clear_cache() -> None:
    base = app_cache_dir()
    if not os.path.isdir(base):
        os.makedirs(base, exist_ok=True)
        return
    for name in os.listdir(base):
        path = os.path.join(base, name)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except OSError:
            pass
    os.makedirs(base, exist_ok=True)

def cleanup_cache() -> None:
    """Small startup cleanup: removes stale cache files and caps icon cache size."""
    base = app_cache_dir()

    icons_dir = os.path.join(base, "icons")
    if os.path.isdir(icons_dir):
        for root, _, files in os.walk(icons_dir):
            for name in files:
                path = os.path.join(root, name)
                _remove_if_old(path, 1 if name.startswith(".tmp_") else ICON_MAX_AGE_DAYS)

    schemas_dir = os.path.join(base, "schemas")
    if os.path.isdir(schemas_dir):
        for root, _, files in os.walk(schemas_dir):
            for name in files:
                if name.startswith(".tmp_"):
                    _remove_if_old(os.path.join(root, name), 1)

    users_dir = os.path.join(base, "users")
    if os.path.isdir(users_dir):
        for root, _, files in os.walk(users_dir):
            for name in files:
                if name == "achievements.json" or name.startswith(".tmp_"):
                    _remove_if_old(os.path.join(root, name), USER_MAX_AGE_DAYS)

    _prune_icon_cache_by_size(MAX_ICON_CACHE_MB)