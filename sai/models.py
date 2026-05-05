from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Achievement:
    appid: int
    game_name: str
    apiname: str
    name: str
    description: str
    icon_url: str
    unlock_time: int

    def unlock_dt(self) -> Optional[datetime]:
        if self.unlock_time and self.unlock_time > 0:
            return datetime.fromtimestamp(self.unlock_time)
        return None
