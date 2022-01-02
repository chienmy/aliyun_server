from datetime import datetime, timedelta
from typing import Tuple


class Utils(object):

    @staticmethod
    def get_today_date() -> str:
        return datetime.today().strftime("%Y%m%d")

    @staticmethod
    def get_week_range() -> Tuple[str, str]:
        today = datetime.utcnow()
        last_week = today - timedelta(days=7)
        return today.strftime("%Y-%m-%dT%H:%M:%SZ"), last_week.strftime("%Y-%m-%dT%H:%M:%SZ")
