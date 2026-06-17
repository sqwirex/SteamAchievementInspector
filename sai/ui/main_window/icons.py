from PyQt6 import QtCore, QtGui
from PyQt6.QtNetwork import QNetworkReply, QNetworkRequest

from sai.storage.cache import read_icon_bytes, write_icon_bytes

class IconsMixin:

    def _load_icon_from_disk_cache(self, url: str) -> bool:
        if not url or url in self.icon_cache:
            return bool(url in self.icon_cache)
        data = read_icon_bytes(url)
        if not data:
            return False
        pix = QtGui.QPixmap()
        if not pix.loadFromData(data):
            return False
        self.icon_cache[url] = QtGui.QIcon(pix)
        return True

    def _enqueue_icon_url(self, url: str, *, front: bool = False) -> None:
        if not url:
            return
        if url not in self.icon_cache and self._load_icon_from_disk_cache(url):
            self._apply_loaded_icon_to_table(url)
            return
        if url in self.icon_cache or url in self.icon_downloading or url in self._pending_icon_url_set:
            return
        if front:
            self._pending_icon_urls.appendleft(url)
        else:
            self._pending_icon_urls.append(url)
        self._pending_icon_url_set.add(url)

    def _schedule_visible_icon_load(self) -> None:
        if self.icons_enabled and hasattr(self, "visible_icon_timer") and not self.visible_icon_timer.isActive():
            self.visible_icon_timer.start()

    def _queue_visible_icons(self):
        if not self.icons_enabled or self.table.rowCount() <= 0:
            return

        viewport = self.table.viewport()
        first = self.table.rowAt(0)
        last = self.table.rowAt(max(0, viewport.height() - 1))
        if first < 0:
            first = 0
        if last < 0:
            last = min(self.table.rowCount() - 1, first + 40)

        first = max(0, first - 10)
        last = min(self.table.rowCount() - 1, last + 10)
        for row in range(first, last + 1):
            self._enqueue_icon_url(self.table_model.icon_url_at(row), front=True)
        self._kick_icon_prefetch()

    def _stop_icon_downloads(self):
        self._pending_icon_urls.clear()
        self._pending_icon_url_set.clear()
        for reply in list(self.icon_replies.values()):
            if reply.isRunning():
                reply.abort()
        self.icon_replies.clear()
        self.icon_downloading.clear()

    def _kick_icon_prefetch(self):
        if not self.icons_enabled:
            self._pending_icon_urls.clear()
            self._pending_icon_url_set.clear()
            return

        while self._pending_icon_urls and len(self.icon_downloading) < self.max_icon_downloads:
            url = self._pending_icon_urls.popleft()
            self._pending_icon_url_set.discard(url)
            if url in self.icon_cache or url in self.icon_downloading:
                continue
            self.icon_downloading.add(url)
            req = QNetworkRequest(QtCore.QUrl(url))
            reply = self.net.get(req)
            self.icon_replies[url] = reply

    def _apply_loaded_icon_to_table(self, url: str) -> None:
        icon = self.icon_cache.get(url)
        if not icon:
            return
        rows = self.table_model.set_icon_for_url(url, icon)
        if rows:
            self.table.viewport().update()

    def _on_icon_loaded(self, reply: QNetworkReply):
        url = reply.url().toString()
        loaded = False
        try:
            self.icon_replies.pop(url, None)
            if self.icons_enabled and reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll().data()
                pix = QtGui.QPixmap()
                if pix.loadFromData(data):
                    self.icon_cache[url] = QtGui.QIcon(pix)
                    write_icon_bytes(url, data)
                    self._update_cache_button_text(force=True)
                    loaded = True
        finally:
            reply.deleteLater()
            self.icon_downloading.discard(url)
            if loaded:
                self._apply_loaded_icon_to_table(url)
            self._queue_visible_icons()