"""Health tracking tool for weight, biometrics, and health metrics."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from nanobot.agent.tools.base import Tool


class HealthTrackerTool(Tool):
    """Tool to track weight, biometrics, and health metrics over time."""

    def __init__(self, workspace: Path | None = None, timezone: str = "UTC"):
        self._workspace = workspace or Path.cwd()
        self._tz = timezone
        self._data_dir = self._workspace / "health_data"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._weight_path = self._data_dir / "weight.json"
        self._biometrics_path = self._data_dir / "biometrics.json"

    def _now(self) -> datetime:
        try:
            return datetime.now(tz=ZoneInfo(self._tz))
        except Exception:
            return datetime.now().astimezone()

    def _today_str(self) -> str:
        return self._now().strftime("%Y-%m-%d")

    def _now(self) -> datetime:
        try:
            return datetime.now(tz=ZoneInfo(self._tz))
        except Exception:
            return datetime.now().astimezone()

    def _today_str(self) -> str:
        return self._now().strftime("%Y-%m-%d")

    def _load_json(self, path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"entries": []}

    def _save_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def name(self) -> str:
        return "health_tracker"

    @property
    def description(self) -> str:
        return (
            "Track weight, biometrics, and health metrics. "
            "Actions: log_weight, view_weight, log_biometric, view_biometrics, "
            "view_all_biometrics, delete_weight, delete_biometric."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "log_weight", "view_weight", "delete_weight",
                        "log_biometric", "view_biometrics", "view_all_biometrics", "delete_biometric",
                    ],
                },
                "weight_kg": {"type": "number", "description": "Weight in kg"},
                "weight_lbs": {"type": "number", "description": "Weight in lbs (auto-converted to kg)"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format (defaults to now)"},
                "time": {"type": "string", "description": "Time in HH:MM format (defaults to now)"},
                "biometric_type": {
                    "type": "string",
                    "enum": list(BIOMETRIC_TYPES.keys()),
                    "description": "Type of biometric measurement",
                },
                "value": {"type": "string", "description": "Biometric value (e.g., '120/80' for BP, '72' for HR)"},
                "notes": {"type": "string", "description": "Additional notes"},
                "entry_index": {"type": "integer", "description": "Index of entry to delete"},
                "start_date": {"type": "string", "description": "Start date for range view (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "End date for range view (YYYY-MM-DD)"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        weight_kg: float | None = None,
        weight_lbs: float | None = None,
        date: str | None = None,
        time: str | None = None,
        biometric_type: str | None = None,
        value: str | None = None,
        notes: str | None = None,
        entry_index: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> str:
        if action == "log_weight":
            return self._log_weight(weight_kg, weight_lbs, date, time, notes)
        elif action == "view_weight":
            return self._view_weight(start_date, end_date)
        elif action == "delete_weight":
            return self._delete_weight(entry_index)
        elif action == "log_biometric":
            return self._log_biometric(biometric_type, value, date, time, notes)
        elif action == "view_biometrics":
            return self._view_biometrics(biometric_type, start_date, end_date)
        elif action == "view_all_biometrics":
            return self._view_all_biometrics(date)
        elif action == "delete_biometric":
            return self._delete_biometric(entry_index)
        return f"Unknown action: {action}."

    def _log_weight(
        self,
        weight_kg: float | None,
        weight_lbs: float | None,
        date: str | None,
        time: str | None,
        notes: str | None,
    ) -> str:
        if weight_kg is None and weight_lbs is None:
            return "Error: provide weight_kg or weight_lbs."
        if weight_lbs is not None:
            weight_kg = round(weight_lbs * 0.453592, 1)

        now = self._now()
        entry = {
            "date": date or now.strftime("%Y-%m-%d"),
            "time": time or now.strftime("%H:%M"),
            "timestamp": now.isoformat(),
            "weight_kg": weight_kg,
            "weight_lbs": round(weight_kg * 2.20462, 1),
            "notes": notes or "",
        }

        data = self._load_json(self._weight_path)
        data["entries"].append(entry)
        data["entries"].sort(key=lambda e: e.get("date", "") + e.get("time", ""))
        self._save_json(self._weight_path, data)

        lines = [f"Logged weight: {weight_kg}kg ({round(weight_kg * 2.20462, 1)}lbs) on {entry['date']} at {entry['time']}"]
        if len(data["entries"]) >= 2:
            prev = data["entries"][-2]
            diff = round(weight_kg - prev["weight_kg"], 1)
            sign = "+" if diff > 0 else ""
            lines.append(f"Change from last: {sign}{diff}kg ({sign}{round(diff * 2.20462, 1)}lbs)")
        if notes:
            lines.append(f"Notes: {notes}")
        return "\n".join(lines)

    def _view_weight(self, start_date: str | None, end_date: str | None) -> str:
        data = self._load_json(self._weight_path)
        entries = data.get("entries", [])
        if not entries:
            return "No weight entries logged."

        if start_date:
            entries = [e for e in entries if e.get("date", "") >= start_date]
        if end_date:
            entries = [e for e in entries if e.get("date", "") <= end_date]
        if not entries:
            return f"No weight entries in the specified date range."

        lines = [f"Weight history ({len(entries)} entries):", ""]
        for i, entry in enumerate(entries):
            line = f"  [{i}] {entry['date']} {entry.get('time', '')} - {entry['weight_kg']}kg ({entry['weight_lbs']}lbs)"
            if entry.get("notes"):
                line += f" ({entry['notes']})"
            lines.append(line)

        if len(entries) >= 2:
            first_w = entries[0]["weight_kg"]
            last_w = entries[-1]["weight_kg"]
            diff = round(last_w - first_w, 1)
            sign = "+" if diff > 0 else ""
            lines.append("")
            lines.append(f"Range: {entries[0]['date']} to {entries[-1]['date']}")
            lines.append(f"Change: {sign}{diff}kg ({sign}{round(diff * 2.20462, 1)}lbs)")
            weights = [e["weight_kg"] for e in entries]
            lines.append(f"Min: {min(weights)}kg | Max: {max(weights)}kg | Avg: {round(sum(weights)/len(weights), 1)}kg")

        return "\n".join(lines)

    def _delete_weight(self, entry_index: int | None) -> str:
        if entry_index is None:
            return "Error: entry_index is required."
        data = self._load_json(self._weight_path)
        entries = data.get("entries", [])
        if not entries:
            return "No weight entries to delete."
        if entry_index < 0 or entry_index >= len(entries):
            return f"Invalid index. Valid: 0-{len(entries)-1}."
        deleted = entries.pop(entry_index)
        self._save_json(self._weight_path, data)
        return f"Deleted weight entry: {deleted['date']} - {deleted['weight_kg']}kg."

    def _log_biometric(
        self,
        biometric_type: str | None,
        value: str | None,
        date: str | None,
        time: str | None,
        notes: str | None,
    ) -> str:
        if not biometric_type:
            return f"Error: biometric_type is required. Options: {', '.join(BIOMETRIC_TYPES.keys())}"
        if not value:
            return "Error: value is required."

        if biometric_type not in BIOMETRIC_TYPES:
            return f"Unknown biometric type: {biometric_type}. Options: {', '.join(BIOMETRIC_TYPES.keys())}"

        now = self._now()
        entry = {
            "date": date or now.strftime("%Y-%m-%d"),
            "time": time or now.strftime("%H:%M"),
            "timestamp": now.isoformat(),
            "type": biometric_type,
            "value": value,
            "notes": notes or "",
        }

        data = self._load_json(self._biometrics_path)
        data["entries"].append(entry)
        data["entries"].sort(key=lambda e: e.get("date", "") + e.get("time", ""))
        self._save_json(self._biometrics_path, data)

        info = BIOMETRIC_TYPES[biometric_type]
        unit = f" {info['unit']}" if info["unit"] else ""
        lines = [f"Logged {info['label']}: {value}{unit} on {entry['date']} at {entry['time']}"]
        if notes:
            lines.append(f"Notes: {notes}")
        return "\n".join(lines)

    def _view_biometrics(
        self,
        biometric_type: str | None,
        start_date: str | None,
        end_date: str | None,
    ) -> str:
        if not biometric_type:
            return f"Error: biometric_type is required. Options: {', '.join(BIOMETRIC_TYPES.keys())}"
        if biometric_type not in BIOMETRIC_TYPES:
            return f"Unknown biometric type: {biometric_type}."

        data = self._load_json(self._biometrics_path)
        entries = [e for e in data.get("entries", []) if e.get("type") == biometric_type]
        if not entries:
            return f"No {biometric_type} entries logged."

        if start_date:
            entries = [e for e in entries if e.get("date", "") >= start_date]
        if end_date:
            entries = [e for e in entries if e.get("date", "") <= end_date]
        if not entries:
            return f"No {biometric_type} entries in the specified date range."

        info = BIOMETRIC_TYPES[biometric_type]
        unit = f" {info['unit']}" if info["unit"] else ""
        lines = [f"{info['label']} history ({len(entries)} entries):", ""]
        for i, entry in enumerate(entries):
            line = f"  [{i}] {entry['date']} {entry.get('time', '')} - {entry['value']}{unit}"
            if entry.get("notes"):
                line += f" ({entry['notes']})"
            lines.append(line)
        return "\n".join(lines)

    def _view_all_biometrics(self, date: str | None) -> str:
        data = self._load_json(self._biometrics_path)
        entries = data.get("entries", [])
        if not entries:
            return "No biometric entries logged."

        if date:
            entries = [e for e in entries if e.get("date") == date]
        if not entries:
            display = date or "any date"
            return f"No biometric entries for {display}."

        target_date = entries[-1].get("date", date or "today")
        day_entries = [e for e in entries if e.get("date") == target_date]
        lines = [f"All biometrics for {target_date}:", ""]

        for entry in day_entries:
            info = BIOMETRIC_TYPES.get(entry["type"], {})
            label = info.get("label", entry["type"])
            unit = f" {info.get('unit', '')}" if info.get("unit") else ""
            line = f"  {label}: {entry['value']}{unit}"
            if entry.get("notes"):
                line += f" ({entry['notes']})"
            lines.append(line)

        return "\n".join(lines)

    def _delete_biometric(self, entry_index: int | None) -> str:
        if entry_index is None:
            return "Error: entry_index is required."
        data = self._load_json(self._biometrics_path)
        entries = data.get("entries", [])
        if not entries:
            return "No biometric entries to delete."
        if entry_index < 0 or entry_index >= len(entries):
            return f"Invalid index. Valid: 0-{len(entries)-1}."
        deleted = entries.pop(entry_index)
        self._save_json(self._biometrics_path, data)
        info = BIOMETRIC_TYPES.get(deleted["type"], {})
        return f"Deleted {info.get('label', deleted['type'])}: {deleted['value']} on {deleted['date']}."
