"""Exercise tracking tool for logging workouts and activity."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from nanobot.agent.tools.base import Tool


class ExerciseTrackerTool(Tool):
    """Tool to log exercise and calculate calorie burn."""

    def __init__(self, workspace: Path | None = None, timezone: str = "UTC"):
        self._workspace = workspace or Path.cwd()
        self._tz = timezone
        self._data_dir = self._workspace / "health_data"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._exercise_path = self._data_dir / "exercises.json"

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
        return "exercise_tracker"

    @property
    def description(self) -> str:
        return (
            "Log exercise and calculate calorie burn. "
            "Actions: log_exercise, view_exercises, delete_exercise, daily_exercise, list_exercises."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["log_exercise", "view_exercises", "delete_exercise", "daily_exercise", "list_exercises"],
                },
                "exercise": {"type": "string", "description": "Exercise name (e.g., 'running', 'cycling', 'weight training')"},
                "duration_min": {"type": "number", "description": "Duration in minutes"},
                "calories_burned": {"type": "number", "description": "Calories burned (if known, overrides calculation)"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "notes": {"type": "string", "description": "Additional notes (e.g., '5km pace', 'heavy legs day')"},
                "entry_index": {"type": "integer", "description": "Index of entry to delete"},
                "user_weight_kg": {"type": "number", "description": "User weight in kg (for calorie calculation, defaults to 70kg)"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        exercise: str | None = None,
        duration_min: float | None = None,
        calories_burned: float | None = None,
        date: str | None = None,
        notes: str | None = None,
        entry_index: int | None = None,
        user_weight_kg: float | None = None,
        **kwargs: Any,
    ) -> str:
        if action == "log_exercise":
            return self._log_exercise(exercise, duration_min, calories_burned, date, notes, user_weight_kg)
        elif action == "view_exercises":
            return self._view_exercises(date)
        elif action == "delete_exercise":
            return self._delete_exercise(entry_index)
        elif action == "daily_exercise":
            return self._daily_exercise(date)
        elif action == "list_exercises":
            return self._list_exercises()
        return f"Unknown action: {action}."

    def _log_exercise(
        self,
        exercise: str | None,
        duration_min: float | None,
        calories_burned: float | None,
        date: str | None,
        notes: str | None,
        user_weight_kg: float | None,
    ) -> str:
        if not exercise:
            return f"Error: exercise name is required. Common: {', '.join(list(COMMON_EXERCISES.keys())[:10])}..."
        if duration_min is None and calories_burned is None:
            return "Error: provide duration_min or calories_burned."

        now = self._now()
        display_date = date or now.strftime("%Y-%m-%d")
        weight = user_weight_kg or 70

        calculated_cal = None
        if duration_min is not None and calories_burned is None:
            exercise_key = exercise.lower().strip()
            matched = None
            for name, info in COMMON_EXERCISES.items():
                if exercise_key == name or exercise_key in name or name in exercise_key:
                    matched = info
                    break
            if matched:
                calculated_cal = round(matched["calories_per_min_per_kg"] * duration_min * weight)

        final_cal = calories_burned or calculated_cal or 0

        entry = {
            "date": display_date,
            "time": now.strftime("%H:%M"),
            "timestamp": now.isoformat(),
            "exercise": exercise,
            "duration_min": duration_min or 0,
            "calories_burned": final_cal,
            "notes": notes or "",
        }

        data = self._load_json(self._exercise_path)
        data["entries"].append(entry)
        data["entries"].sort(key=lambda e: e.get("date", "") + e.get("time", ""))
        self._save_json(self._exercise_path, data)

        lines = [f"Logged: {exercise}"]
        if duration_min:
            lines.append(f"  Duration: {duration_min} min")
        lines.append(f"  Calories burned: {final_cal} kcal")
        if calculated_cal and not calories_burned:
            lines.append(f"  (estimated for {weight}kg body weight)")
        if notes:
            lines.append(f"  Notes: {notes}")
        lines.append(f"  Date: {display_date}")

        daily_total = sum(
            e.get("calories_burned", 0) for e in data["entries"] if e.get("date") == display_date
        )
        lines.append(f"\nDaily exercise total: {daily_total} kcal burned")
        return "\n".join(lines)

    def _view_exercises(self, date: str | None) -> str:
        data = self._load_json(self._exercise_path)
        entries = data.get("entries", [])
        if not entries:
            return "No exercise entries logged."

        if date:
            entries = [e for e in entries if e.get("date") == date]
        if not entries:
            display = date or "any date"
            return f"No exercise entries for {display}."

        lines = [f"Exercise log ({len(entries)} entries):", ""]
        total_cal = 0
        total_min = 0
        for i, entry in enumerate(entries):
            line = f"  [{i}] {entry['date']} {entry.get('time', '')} - {entry['exercise']}"
            if entry.get("duration_min"):
                line += f" ({entry['duration_min']} min)"
            line += f" - {entry.get('calories_burned', 0)} kcal"
            if entry.get("notes"):
                line += f" ({entry['notes']})"
            lines.append(line)
            total_cal += entry.get("calories_burned", 0)
            total_min += entry.get("duration_min", 0)

        lines.append("")
        lines.append(f"Total: {total_min} min exercise | {total_cal} kcal burned")
        return "\n".join(lines)

    def _delete_exercise(self, entry_index: int | None) -> str:
        if entry_index is None:
            return "Error: entry_index is required."
        data = self._load_json(self._exercise_path)
        entries = data.get("entries", [])
        if not entries:
            return "No exercise entries to delete."
        if entry_index < 0 or entry_index >= len(entries):
            return f"Invalid index. Valid: 0-{len(entries)-1}."
        deleted = entries.pop(entry_index)
        self._save_json(self._exercise_path, data)
        return f"Deleted: {deleted['exercise']} ({deleted.get('duration_min', 0)} min, {deleted.get('calories_burned', 0)} kcal)."

    def _daily_exercise(self, date: str | None) -> str:
        data = self._load_json(self._exercise_path)
        entries = data.get("entries", [])
        display_date = date or self._today_str()
        day_entries = [e for e in entries if e.get("date") == display_date]

        if not day_entries:
            return f"No exercise logged for {display_date}."

        lines = [f"Exercise summary for {display_date}:", ""]
        total_cal = 0
        total_min = 0
        for entry in day_entries:
            cal = entry.get("calories_burned", 0)
            dur = entry.get("duration_min", 0)
            lines.append(f"  {entry['exercise']}: {dur} min | {cal} kcal burned")
            total_cal += cal
            total_min += dur

        lines.append("")
        lines.append(f"Total: {total_min} min | {total_cal} kcal burned")
        return "\n".join(lines)

    def _list_exercises(self) -> str:
        lines = ["Known exercises and calorie burn rates (per min per kg body weight):", ""]
        by_category: dict[str, list] = {}
        for name, info in COMMON_EXERCISES.items():
            cat = info.get("category", "other")
            by_category.setdefault(cat, []).append((name, info))

        for cat in ["cardio", "strength", "flexibility"]:
            if cat in by_category:
                lines.append(f"  {cat.title()}:")
                for name, info in sorted(by_category[cat]):
                    cpm = info["calories_per_min_per_kg"]
                    lines.append(f"    {name}: {cpm} cal/min/kg ({round(cpm * 70)} cal/min for 70kg person)")
                lines.append("")

        return "\n".join(lines)
