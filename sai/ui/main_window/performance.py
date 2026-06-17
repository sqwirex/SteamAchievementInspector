import os
from typing import Optional

class PerformanceMixin:

    @staticmethod
    def _auto_worker_limit(cpu_count: int) -> int:
        cpu = max(1, int(cpu_count or 1))
        if cpu <= 2:
            return 2
        if cpu <= 4:
            return 3
        if cpu <= 8:
            return 4
        if cpu <= 12:
            return 6
        return 8

    def _limits_for_performance_mode(self, mode: Optional[str] = None) -> tuple[int, int]:
        cpu = max(1, int(os.cpu_count() or 1))
        mode = mode or self.performance_mode
        if mode == "eco":
            return 2, 2
        if mode == "fast":
            workers = min(6, max(4, cpu // 2 + 1))
            icons = min(5, max(3, workers))
            return workers, icons
        workers = self._auto_worker_limit(cpu)
        icons = min(6, max(3, workers))
        return workers, icons

    def _apply_performance_limits(self) -> None:
        self.max_workers, self.max_icon_downloads = self._limits_for_performance_mode()
        if hasattr(self, "threadpool"):
            self.threadpool.setMaxThreadCount(self.max_workers + max(2, self.max_icon_downloads // 2))