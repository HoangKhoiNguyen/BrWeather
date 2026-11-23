"""OpenAQ API v3 client (station measurements).

Limits: 60 requests/minute and 2,000/hour per key. Repeated 429s can get the key banned,
so every request is spaced out and a 429 waits for the next window.
"""
import time
from collections.abc import Callable, Iterator
from datetime import datetime

import requests

BASE_URL = "https://api.openaq.org/v3"


class SourceError(RuntimeError):
    """The source (not our code) failed: e.g. the rate limit kept refusing us."""


class OpenAQClient:
    def __init__(self, api_key: str, min_interval_s: float = 1.1):
        self._session = requests.Session()
        self._session.headers["X-API-Key"] = api_key
        self._min_interval = min_interval_s
        self._last_call = 0.0

    def _get(self, path: str, params: dict | None = None) -> dict:
        for _ in range(3):
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            resp = self._session.get(f"{BASE_URL}{path}", params=params, timeout=30)
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("x-ratelimit-reset", 60)))
                continue
            resp.raise_for_status()
            return resp.json()
        raise SourceError(f"OpenAQ rate limit kept failing for {path}")

    def location(self, location_id: int) -> dict:
        return self._get(f"/locations/{location_id}")["results"][0]

    @staticmethod
    def pm25_sensor_id(location: dict) -> int | None:
        for sensor in location.get("sensors", []):
            if sensor["parameter"]["name"] == "pm25":
                return sensor["id"]
        return None

    def hourly(
        self,
        sensor_id: int,
        date_from: datetime,
        date_to: datetime,
        on_page: Callable[[str, dict], None] | None = None,
    ) -> Iterator[tuple[datetime, float | None]]:
        """Yield (hour start in UTC, value) for every hour OpenAQ has; missing hours are simply absent.

        on_page(request, payload) is called with every raw page, so the caller can keep it in raw_payloads.
        """
        page, limit = 1, 1000
        while True:
            data = self._get(
                f"/sensors/{sensor_id}/hours",
                {
                    "datetime_from": date_from.isoformat(),
                    "datetime_to": date_to.isoformat(),
                    "limit": limit,
                    "page": page,
                },
            )
            if on_page is not None:
                on_page(f"/sensors/{sensor_id}/hours from={date_from.isoformat()} to={date_to.isoformat()} page={page}", data)
            results = data.get("results", [])
            for item in results:
                start = datetime.fromisoformat(item["period"]["datetimeFrom"]["utc"].replace("Z", "+00:00"))
                yield start, item.get("value")
            if len(results) < limit:
                return
            page += 1
