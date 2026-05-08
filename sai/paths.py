import os
import sys


def app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.getcwd())


def app_cache_dir() -> str:
    path = os.path.join(app_base_dir(), "cache")
    os.makedirs(path, exist_ok=True)
    return path


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    return os.path.join(base_path, relative_path)


def app_exports_dir() -> str:
    path = os.path.join(app_base_dir(), "exports")
    os.makedirs(path, exist_ok=True)
    return path