"""Inventory OpenAQ PM2.5 sensor metadata within 25 km of Hanoi center."""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "audit"
BASE = "https://api.openaq.org/v3"
FIELDS = (
    "location_id", "location_name", "locality", "latitude", "longitude",
    "timezone", "provider", "owner", "license", "is_mobile", "is_monitor",
    "sensor_id", "parameter_id", "parameter_name", "unit",
    "datetime_first", "datetime_last",
)


def utc(value):
    if isinstance(value, dict):
        value = value.get("utc")
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()


class Client:
    def __init__(self, key):
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = key
        self.calls = 0
        self.remaining = None
        self.last_call = 0.0

    def get(self, path, params=None):
        for attempt in range(4):
            if self.calls >= 1900:
                raise RuntimeError("Đã dùng 1.900 request; dừng để giữ dưới giới hạn giờ")
            time.sleep(max(0, 2.1 - (time.monotonic() - self.last_call)))
            self.last_call = time.monotonic()
            self.calls += 1
            try:
                response = self.session.get(BASE + path, params=params, timeout=20)
            except requests.RequestException as exc:
                if attempt == 3:
                    raise RuntimeError(f"Lỗi mạng: {type(exc).__name__}") from None
                time.sleep(2 ** attempt)
                continue
            self.remaining = response.headers.get("x-ratelimit-remaining", self.remaining)
            if response.status_code in (401, 403):
                raise RuntimeError(f"HTTP {response.status_code}: kiểm tra khóa hoặc quyền truy cập")
            if response.status_code == 429 or response.status_code == 408 or response.status_code >= 500:
                if attempt == 3:
                    raise RuntimeError(f"HTTP {response.status_code}: hết lượt thử tại {path}")
                retry = response.headers.get("Retry-After")
                time.sleep(min(120, int(retry) if retry and retry.isdigit() else 2 ** (attempt + 1)))
                continue
            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code} tại {path}")
            return response.json()
        raise RuntimeError("Hết lượt thử")


def main():
    load_dotenv(ROOT / ".env")
    key = os.getenv("OPENAQ_API_KEY")
    if not key or key == "your_openaq_key":
        raise RuntimeError("OPENAQ_API_KEY chưa được đặt trong .env")
    client = Client(key)
    locations = []
    page = 1
    while True:
        data = client.get("/locations", {
            "coordinates": "21.0285,105.8542", "radius": 25000,
            "parameters_id": 2, "limit": 100, "page": page,
            "order_by": "id", "sort_order": "asc",
        })
        batch = data["results"]
        locations.extend(batch)
        found = data.get("meta", {}).get("found")
        if not batch or (found is not None and len(locations) >= int(found)) or len(batch) < 100:
            break
        page += 1
    pages = page

    inventory = []
    sensor_details = {}
    seen = set()
    pm_locations = set()
    for location in locations:
        for sensor in location.get("sensors", []):
            parameter = sensor.get("parameter") or {}
            if parameter.get("name") != "pm25":
                continue
            pm_locations.add(location["id"])
            sensor_id = sensor["id"]
            if sensor_id in seen:
                continue
            seen.add(sensor_id)
            detail_response = client.get(f"/sensors/{sensor_id}")
            detail = detail_response["results"][0]
            sensor_details[str(sensor_id)] = detail
            parameter = detail.get("parameter") or parameter
            coords = location.get("coordinates") or {}
            inventory.append({
                "location_id": location["id"],
                "location_name": location.get("name"),
                "locality": location.get("locality"),
                "latitude": coords.get("latitude"),
                "longitude": coords.get("longitude"),
                "timezone": location.get("timezone"),
                "provider": (location.get("provider") or {}).get("name"),
                "owner": (location.get("owner") or {}).get("name"),
                "license": json.dumps(location["licenses"], ensure_ascii=False) if location.get("licenses") is not None else None,
                "is_mobile": location.get("isMobile"),
                "is_monitor": location.get("isMonitor"),
                "sensor_id": sensor_id,
                "parameter_id": parameter.get("id"),
                "parameter_name": parameter.get("name"),
                "unit": parameter.get("units"),
                "datetime_first": utc(detail.get("datetimeFirst")),
                "datetime_last": utc(detail.get("datetimeLast")),
            })

    inventory.sort(key=lambda row: row["datetime_last"] or "", reverse=True)
    assert len(seen) == len(inventory)
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "openaq_hanoi_sensor_inventory.csv"
    json_path = OUT / "openaq_hanoi_sensor_inventory.json"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(inventory)
    with json_path.open("w", encoding="utf-8") as file:
        json.dump({
            "survey": {"center": [21.0285, 105.8542], "radius_m": 25000,
                       "parameter_id": 2, "pages": pages},
            "locations": locations, "sensor_details": sensor_details,
            "inventory": inventory,
        }, file, ensure_ascii=False, indent=2)
    with csv_path.open(encoding="utf-8", newline="") as file:
        assert len(list(csv.DictReader(file))) == len(inventory)
    with json_path.open(encoding="utf-8") as file:
        assert len(json.load(file)["inventory"]) == len(inventory)

    times = [row["datetime_last"] for row in inventory if row["datetime_last"]]
    print(f"Tổng số trang location: {pages}")
    print(f"Tổng số location nhận được: {len(locations)}")
    print(f"Tổng số location có PM2.5: {len(pm_locations)}")
    print(f"Tổng số sensor PM2.5: {len(inventory)}")
    print(f"Số sensor có datetime_first: {sum(bool(row['datetime_first']) for row in inventory)}")
    print(f"Số sensor có datetime_last: {len(times)}")
    print(f"datetime_last mới nhất: {max(times) if times else 'null'}")
    print(f"datetime_last cũ nhất: {min(times) if times else 'null'}")
    print(f"Số request đã sử dụng: {client.calls}; rate-limit còn lại: {client.remaining or 'không có header'}")
    print(f"CSV: {csv_path}\nJSON: {json_path}")
    print("sensor_id | location_name | provider | datetime_first | datetime_last | unit")
    for row in inventory[:10]:
        print(" | ".join(str(row[name] or "") for name in (
            "sensor_id", "location_name", "provider", "datetime_first", "datetime_last", "unit")))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except (RuntimeError, KeyError, ValueError, requests.RequestException) as exc:
        print(f"Inventory failed: {exc}")
        raise SystemExit(1)
