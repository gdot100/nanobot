"""Fitbit and Apple Health integration tool for syncing health data."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import httpx

from nanobot.agent.tools.base import Tool


class DeviceSyncTool(Tool):
    """Tool to sync health data from Fitbit and Apple Health."""

    def __init__(self, workspace: Path | None = None, timezone: str = "UTC"):
        self._workspace = workspace or Path.cwd()
        self._tz = timezone
        self._data_dir = self._workspace / "health_data"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._fitbit_data_path = self._data_dir / "fitbit_cache.json"
        self._apple_health_path = self._data_dir / "apple_health_cache.json"
        self._config_path = self._workspace / "device_config.json"
        self._config = self._load_config()

    def _now(self) -> datetime:
        try:
            return datetime.now(tz=ZoneInfo(self._tz))
        except Exception:
            return datetime.now().astimezone()

    def _today_str(self) -> str:
        return self._now().strftime("%Y-%m-%d")

    def _load_config(self) -> dict:
        if self._config_path.exists():
            try:
                return json.loads(self._config_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_config(self) -> None:
        self._config_path.write_text(
            json.dumps(self._config, indent=2), encoding="utf-8"
        )

    def _load_cache(self, path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_cache(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    async def _refresh_fitbit_token(self) -> str | None:
        fitbit_config = self._config.get("fitbit", {})
        client_id = fitbit_config.get("client_id") or os.environ.get("FITBIT_CLIENT_ID")
        client_secret = fitbit_config.get("client_secret") or os.environ.get("FITBIT_CLIENT_SECRET")
        refresh_token = fitbit_config.get("refresh_token") or os.environ.get("FITBIT_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            return None

        import base64
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.fitbit.com/oauth2/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                    headers={"Authorization": f"Basic {credentials}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._config["fitbit"]["access_token"] = data["access_token"]
                    self._config["fitbit"]["refresh_token"] = data.get("refresh_token", refresh_token)
                    self._config["fitbit"]["token_expires_at"] = time.time() + data.get("expires_in", 28800)
                    self._save_config()
                    return data["access_token"]
        except Exception:
            pass
        return None

    async def _get_fitbit_token(self) -> str | None:
        fitbit_config = self._config.get("fitbit", {})
        token = fitbit_config.get("access_token") or os.environ.get("FITBIT_ACCESS_TOKEN")
        expires_at = fitbit_config.get("token_expires_at", 0)

        if not token:
            return None

        if expires_at and time.time() > expires_at - 300:
            refreshed = await self._refresh_fitbit_token()
            if refreshed:
                return refreshed

        return token

    @property
    def name(self) -> str:
        return "device_sync"

    @property
    def description(self) -> str:
        return (
            "Sync health data from Fitbit and Apple Health. "
            "Actions: setup_fitbit, sync_fitbit, view_fitbit, "
            "import_apple_health, view_apple_health, config."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "setup_fitbit", "sync_fitbit", "view_fitbit",
                        "import_apple_health", "view_apple_health",
                        "config",
                    ],
                },
                "client_id": {"type": "string", "description": "Fitbit OAuth client ID"},
                "client_secret": {"type": "string", "description": "Fitbit OAuth client secret"},
                "access_token": {"type": "string", "description": "Fitbit access token"},
                "refresh_token": {"type": "string", "description": "Fitbit refresh token"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "data_type": {
                    "type": "string",
                    "enum": ["activities", "heart_rate", "sleep", "nutrition", "weight", "body"],
                    "description": "Type of data to sync",
                },
                "xml_path": {"type": "string", "description": "Path to Apple Health export.xml file"},
                "health_type": {"type": "string", "description": "Apple Health type to view (e.g., 'Heart Rate', 'Body Mass')"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        date: str | None = None,
        data_type: str | None = None,
        xml_path: str | None = None,
        health_type: str | None = None,
        **kwargs: Any,
    ) -> str:
        if action == "setup_fitbit":
            return self._setup_fitbit(client_id, client_secret, access_token, refresh_token)
        elif action == "sync_fitbit":
            return await self._sync_fitbit(date, data_type)
        elif action == "view_fitbit":
            return self._view_fitbit(data_type, date)
        elif action == "import_apple_health":
            return self._import_apple_health(xml_path)
        elif action == "view_apple_health":
            return self._view_apple_health(health_type, date)
        elif action == "config":
            return self._view_config()
        return f"Unknown action: {action}."

    def _setup_fitbit(
        self,
        client_id: str | None,
        client_secret: str | None,
        access_token: str | None,
        refresh_token: str | None,
    ) -> str:
        self._config.setdefault("fitbit", {})
        if client_id:
            self._config["fitbit"]["client_id"] = client_id
        if client_secret:
            self._config["fitbit"]["client_secret"] = client_secret
        if access_token:
            self._config["fitbit"]["access_token"] = access_token
        if refresh_token:
            self._config["fitbit"]["refresh_token"] = refresh_token
        if access_token:
            self._config["fitbit"]["token_expires_at"] = time.time() + 28800
        self._save_config()

        has_refresh = bool(self._config["fitbit"].get("refresh_token"))
        has_token = bool(self._config["fitbit"].get("access_token"))
        if has_refresh and has_token:
            return "Fitbit credentials saved. Token will auto-refresh. Ready to sync."
        if has_token and not has_refresh:
            return "Access token saved but no refresh token. Token will expire in 8 hours. Please re-setup with refresh_token for auto-refresh."
        return (
            "Fitbit setup started. To get your credentials:\n"
            "1. Go to https://dev.fitbit.com/apps/new\n"
            "2. Create an app and note your Client ID and Client Secret\n"
            "3. Use the Fitbit OAuth flow to get an access token and refresh token\n"
            "4. Run: device_sync(action='setup_fitbit', access_token='...', refresh_token='...')"
        )

    async def _sync_fitbit(self, date: str | None, data_type: str | None) -> str:
        token = await self._get_fitbit_token()
        if not token:
            return (
                "No Fitbit access token found. "
                "Set it up with: device_sync(action='setup_fitbit', access_token='...', refresh_token='...')"
            )

        sync_date = date or self._today_str()
        results = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {"Authorization": f"Bearer {token}"}

            if data_type is None or data_type == "activities":
                try:
                    resp = await client.get(
                        f"https://api.fitbit.com/1/user/-/activities/date/{sync_date}.json",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        summary = data.get("summary", {})
                        cache = self._load_cache(self._fitbit_data_path)
                        cache.setdefault("activities", {})[sync_date] = summary
                        self._save_cache(self._fitbit_data_path, cache)
                        steps = summary.get("steps", 0)
                        cal = summary.get("caloriesOut", 0)
                        dist = round(summary.get("distances", [{}])[0].get("distance", 0), 2)
                        results.append(f"Activities: {steps} steps | {cal} kcal out | {dist} km")
                    elif resp.status_code == 401:
                        results.append("Activities: Token expired. Re-setup with refresh_token.")
                    else:
                        results.append(f"Activities: Failed (HTTP {resp.status_code})")
                except Exception as e:
                    results.append(f"Activities: Error - {e}")

            if data_type is None or data_type == "heart_rate":
                try:
                    resp = await client.get(
                        f"https://api.fitbit.com/1/user/-/activities/heart/date/{sync_date}/1d.json",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        hr_data = data.get("activities-heart", [{}])[0]
                        value = hr_data.get("value", {})
                        cache = self._load_cache(self._fitbit_data_path)
                        cache.setdefault("heart_rate", {})[sync_date] = value
                        self._save_cache(self._fitbit_data_path, cache)
                        resting = value.get("restingHeartRate", "N/A")
                        zones = value.get("heartRateZones", [])
                        results.append(f"Heart Rate: resting {resting} bpm | {len(zones)} zones recorded")
                    elif resp.status_code == 401:
                        results.append("Heart Rate: Token expired.")
                    else:
                        results.append(f"Heart Rate: Failed (HTTP {resp.status_code})")
                except Exception as e:
                    results.append(f"Heart Rate: Error - {e}")

            if data_type is None or data_type == "sleep":
                try:
                    resp = await client.get(
                        f"https://api.fitbit.com/1.2/user/-/sleep/date/{sync_date}.json",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        sleep_records = data.get("sleep", [])
                        cache = self._load_cache(self._fitbit_data_path)
                        cache.setdefault("sleep", {})[sync_date] = sleep_records
                        self._save_cache(self._fitbit_data_path, cache)
                        if sleep_records:
                            for record in sleep_records:
                                duration = record.get("minutesAsleep", 0)
                                efficiency = record.get("efficiency", 0)
                                results.append(f"Sleep: {duration} min | efficiency {efficiency}%")
                        else:
                            results.append("Sleep: No sleep data for this date")
                    elif resp.status_code == 401:
                        results.append("Sleep: Token expired.")
                    else:
                        results.append(f"Sleep: Failed (HTTP {resp.status_code})")
                except Exception as e:
                    results.append(f"Sleep: Error - {e}")

            if data_type is None or data_type == "nutrition":
                try:
                    resp = await client.get(
                        f"https://api.fitbit.com/1/user/-/foods/log/date/{sync_date}.json",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        summary = data.get("summary", {})
                        cache = self._load_cache(self._fitbit_data_path)
                        cache.setdefault("nutrition", {})[sync_date] = summary
                        self._save_cache(self._fitbit_data_path, cache)
                        cal_in = summary.get("calories", 0)
                        results.append(f"Nutrition: {cal_in} kcal consumed (from Fitbit food log)")
                    elif resp.status_code == 401:
                        results.append("Nutrition: Token expired.")
                    else:
                        results.append(f"Nutrition: Failed (HTTP {resp.status_code})")
                except Exception as e:
                    results.append(f"Nutrition: Error - {e}")

            if data_type is None or data_type == "weight":
                try:
                    resp = await client.get(
                        f"https://api.fitbit.com/1/user/-/body/log/weight/date/{sync_date}.json",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        weights = data.get("weight", [])
                        cache = self._load_cache(self._fitbit_data_path)
                        cache.setdefault("weight", {})[sync_date] = weights
                        self._save_cache(self._fitbit_data_path, cache)
                        if weights:
                            for w in weights:
                                results.append(f"Weight: {w.get('weight', '?')} kg | BMI: {w.get('bmi', '?')}")
                        else:
                            results.append("Weight: No weight data for this date")
                    elif resp.status_code == 401:
                        results.append("Weight: Token expired.")
                    else:
                        results.append(f"Weight: Failed (HTTP {resp.status_code})")
                except Exception as e:
                    results.append(f"Weight: Error - {e}")

        return f"Fitbit sync for {sync_date}:\n" + "\n".join(f"  {r}" for r in results)

    def _import_apple_health(self, xml_path: str | None) -> str:
        if not xml_path:
            return (
                "Apple Health import requires an XML export file.\n\n"
                "How to export from Apple Health:\n"
                "1. Open the Health app on your iPhone\n"
                "2. Tap your profile picture (top right)\n"
                "3. Scroll down and tap 'Export All Health Data'\n"
                "4. Share the export.zip file to your computer\n"
                "5. Extract the zip - you'll find an export.xml file\n"
                "6. Run: device_sync(action='import_apple_health', xml_path='/path/to/export.xml')\n\n"
                "The import will parse all your health data and cache it for querying."
            )

        path = Path(xml_path)
        if not path.exists():
            return f"File not found: {xml_path}"

        try:
            tree = ET.parse(str(path))
            root = tree.getroot()
        except Exception as e:
            return f"Error parsing XML: {e}"

        records = root.findall("Record")
        workouts = root.findall("Workout")
        all_entries = records + workouts

        if not all_entries:
            return "No health records found in the XML file."

        cache = {"records": [], "summary": {}, "imported_at": self._now().isoformat()}

        type_counts: dict[str, int] = {}
        type_latest: dict[str, dict] = {}

        for entry in all_entries:
            entry_type = entry.get("type", "")
            value = entry.get("value", "")
            unit = entry.get("unit", "")
            start = entry.get("startDate", "")
            end = entry.get("endDate", "")
            source = entry.get("sourceName", "")

            type_counts[entry_type] = type_counts.get(entry_type, 0) + 1

            record = {
                "type": entry_type,
                "value": value,
                "unit": unit,
                "start": start,
                "end": end,
                "source": source,
            }

            if entry_type == "Workout":
                record["duration"] = entry.get("duration", "")
                record["totalDistance"] = entry.get("totalDistance", "")
                record["totalEnergyBurned"] = entry.get("totalEnergyBurned", "")
                record["totalDistanceUnit"] = entry.get("totalDistanceUnit", "")
                record["totalEnergyBurnedUnit"] = entry.get("totalEnergyBurnedUnit", "")

            cache["records"].append(record)

            date_key = start[:10] if len(start) >= 10 else "unknown"
            if entry_type not in type_latest or start > type_latest[entry_type].get("start", ""):
                type_latest[entry_type] = record

        cache["summary"] = {
            "total_records": len(all_entries),
            "type_counts": type_counts,
            "latest": {
                self._apple_type_name(k): v
                for k, v in type_latest.items()
            },
            "date_range": {
                "earliest": min(r.get("start", "9999")[:10] for r in all_entries if r.get("start")),
                "latest": max(r.get("end", r.get("start", "0000"))[:10] for r in all_entries if r.get("end") or r.get("start")),
            },
        }

        self._save_cache(self._apple_health_path, cache)

        lines = [
            f"Apple Health imported: {len(all_entries)} records",
            f"Date range: {cache['summary']['date_range']['earliest']} to {cache['summary']['date_range']['latest']}",
            "",
            "Record types:",
        ]
        for type_key, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            label = self._apple_type_name(type_key)
            lines.append(f"  {label}: {count} entries")

        lines.append("")
        lines.append("Latest values:")
        for type_key, record in sorted(type_latest.items()):
            label = self._apple_type_name(type_key)
            val = record.get("value", "")
            unit = record.get("unit", "")
            date = record.get("start", "")[:10]
            if val:
                lines.append(f"  {label}: {val} {unit} ({date})")

        return "\n".join(lines)

    def _view_apple_health(self, health_type: str | None, date: str | None) -> str:
        cache = self._load_cache(self._apple_health_path)
        if not cache or not cache.get("records"):
            return "No Apple Health data imported. Use import_apple_health action first."

        summary = cache.get("summary", {})

        if not health_type:
            lines = ["Apple Health data summary:", ""]
            lines.append(f"Total records: {summary.get('total_records', 0)}")
            if "date_range" in summary:
                lines.append(f"Date range: {summary['date_range']['earliest']} to {summary['date_range']['latest']}")
            lines.append("")
            lines.append("Available data types:")
            for type_key, count in sorted(summary.get("type_counts", {}).items(), key=lambda x: -x[1]):
                label = self._apple_type_name(type_key)
                lines.append(f"  {label}: {count} entries")
            lines.append("")
            lines.append("Use: device_sync(action='view_apple_health', health_type='Heart Rate')")
            return "\n".join(lines)

        type_key = self._find_apple_type(health_type)
        if not type_key:
            return f"Unknown health type: {health_type}. Available: {', '.join(self._apple_type_name(k) for k in summary.get('type_counts', {}).keys())}"

        records = [r for r in cache["records"] if r.get("type") == type_key]
        if date:
            records = [r for r in records if r.get("start", "")[:10] == date]
        if not records:
            return f"No {self._apple_type_name(type_key)} records found" + (f" for {date}" if date else ".")

        label = self._apple_type_name(type_key)
        lines = [f"{label} ({len(records)} records):", ""]

        display_records = records[-50:] if len(records) > 50 else records
        for r in display_records:
            date_str = r.get("start", "")[:16].replace("T", " ")
            val = r.get("value", "")
            unit = r.get("unit", "")
            line = f"  {date_str} - {val} {unit}".strip()
            lines.append(line)

        if len(records) > 50:
            lines.append(f"  ... ({len(records) - 50} more records)")

        if records:
            numeric = []
            for r in records:
                try:
                    numeric.append(float(r.get("value", 0)))
                except (ValueError, TypeError):
                    pass
            if numeric:
                lines.append("")
                lines.append(f"Min: {min(numeric):.1f} | Max: {max(numeric):.1f} | Avg: {sum(numeric)/len(numeric):.1f}")

        return "\n".join(lines)

    def _view_config(self) -> str:
        lines = ["Device configuration:"]
        if "fitbit" in self._config:
            fb = self._config["fitbit"]
            has_token = bool(fb.get("access_token"))
            has_refresh = bool(fb.get("refresh_token"))
            lines.append(f"  Fitbit: configured (token: {'yes' if has_token else 'no'}, auto-refresh: {'yes' if has_refresh else 'no'})")
        else:
            lines.append("  Fitbit: not configured")
        if "apple_health" in self._config:
            lines.append(f"  Apple Health: imported ({self._config['apple_health'].get('record_count', '?')} records)")
        else:
            lines.append("  Apple Health: not imported")
        return "\n".join(lines)

    @staticmethod
    def _apple_type_name(type_key: str) -> str:
        return APPLE_HEALTH_TYPES.get(type_key, type_key.split(".")[-1])

    @staticmethod
    def _find_apple_type(friendly_name: str) -> str | None:
        name_lower = friendly_name.lower()
        for type_key, label in APPLE_HEALTH_TYPES.items():
            if name_lower == label.lower() or name_lower in label.lower() or label.lower() in name_lower:
                return type_key
        return None
