"""Todo list tool for tracking daily and global tasks."""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from nanobot.agent.tools.base import Tool


class TodoListTool(Tool):
    """Tool to manage daily and global todo lists with automatic day rollover."""

    def __init__(self, workspace: Path | None = None, timezone: str = "UTC"):
        self._workspace = workspace or Path.cwd()
        self._tz = timezone
        self._daily_dir = self._workspace / "todo_daily"
        self._daily_dir.mkdir(parents=True, exist_ok=True)
        self._global_path = self._workspace / "todo_global.json"
        self._history_path = self._workspace / "todo_history.json"

    def _now(self) -> datetime:
        try:
            return datetime.now(tz=ZoneInfo(self._tz))
        except Exception:
            return datetime.now().astimezone()

    def _today_str(self) -> str:
        return self._now().strftime("%Y-%m-%d")

    def _get_daily_path(self, date: str | None = None) -> Path:
        if date is None:
            date = self._today_str()
        return self._daily_dir / f"{date}.json"

    def _load_daily(self, date: str | None = None) -> dict:
        path = self._get_daily_path(date)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"date": date or self._today_str(), "items": []}

    def _save_daily(self, data: dict, date: str | None = None) -> None:
        path = self._get_daily_path(date)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_global(self) -> dict:
        if self._global_path.exists():
            try:
                return json.loads(self._global_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"items": []}

    def _save_global(self, data: dict) -> None:
        self._global_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _load_history(self) -> dict:
        if self._history_path.exists():
            try:
                return json.loads(self._history_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"completed": [], "by_date": {}, "by_month": {}}

    def _save_history(self, data: dict) -> None:
        self._history_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _record_completed(self, item: dict, list_type: str, date: str | None = None) -> None:
        history = self._load_history()

        completed_item = {
            "content": item["content"],
            "completed_at": self._now().isoformat(),
            "list_type": list_type,
            "priority": item.get("priority", "medium"),
            "created_at": item.get("created_at"),
        }

        history["completed"].insert(0, completed_item)
        history["completed"] = history["completed"][:1000]

        today = self._today_str()
        if today not in history["by_date"]:
            history["by_date"][today] = []
        history["by_date"][today].append(completed_item)

        month_key = today[:7]
        if month_key not in history["by_month"]:
            history["by_month"][month_key] = []
        history["by_month"][month_key].append(completed_item)

        self._save_history(history)

    @property
    def name(self) -> str:
        return "todo_list"

    @property
    def description(self) -> str:
        return (
            "Manage daily and global todo lists. "
            "Actions: add, complete, uncomplete, remove, list, clear, move, show_stats, history, log_done. "
            "Use list_type='daily' or 'global'. log_done records work done without a todo."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "add",
                        "complete",
                        "uncomplete",
                        "remove",
                        "list",
                        "clear",
                        "move",
                        "show_stats",
                        "history",
                        "log_done",
                    ],
                    "description": "Action to perform",
                },
                "list_type": {
                    "type": "string",
                    "enum": ["daily", "global"],
                    "description": "Which list to operate on",
                },
                "content": {"type": "string", "description": "Task content (for add)"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Task priority (for add)",
                },
                "index": {
                    "type": "integer",
                    "description": "Task index (for complete/uncomplete/remove/move)",
                },
                "date": {
                    "type": "string",
                    "description": "Date for daily list (YYYY-MM-DD, defaults to today)",
                },
                "target_list": {
                    "type": "string",
                    "description": "Target list for move action (daily or global)",
                },
                "history_date": {
                    "type": "string",
                    "description": "Date for history (YYYY-MM-DD)",
                },
                "history_month": {
                    "type": "string",
                    "description": "Month for history (YYYY-MM)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of items to show (default 20)",
                },
                "notes": {
                    "type": "string",
                    "description": "Notes about what was done (for log_done)",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        list_type: str | None = None,
        content: str | None = None,
        priority: str | None = None,
        index: int | None = None,
        date: str | None = None,
        target_list: str | None = None,
        history_date: str | None = None,
        history_month: str | None = None,
        limit: int | None = None,
        notes: str | None = None,
        **kwargs: Any,
    ) -> str:
        if action == "history":
            return self._get_history(history_date, history_month, limit)

        if action == "log_done":
            return self._log_done(content, notes)

        if not list_type:
            return "Error: list_type is required for this action."

        if list_type == "daily":
            return await self._handle_daily(action, content, priority, index, date, target_list)
        else:
            return self._handle_global(action, content, priority, index, target_list)

    async def _handle_daily(
        self,
        action: str,
        content: str | None,
        priority: str | None,
        index: int | None,
        date: str | None,
        target_list: str | None,
    ) -> str:
        data = self._load_daily(date)

        if action == "add":
            if not content:
                return "Error: content is required to add a task."
            item = {
                "id": len(data["items"]) + 1,
                "content": content,
                "completed": False,
                "priority": priority or "medium",
                "created_at": self._now().isoformat(),
            }
            data["items"].append(item)
            self._save_daily(data, date)
            return f"Added to daily todo: [{item['id']}] {content} (priority: {item['priority']})"

        elif action == "complete":
            if index is None:
                return "Error: index is required to complete a task."
            return self._toggle_complete(data, index, True, date)

        elif action == "uncomplete":
            if index is None:
                return "Error: index is required to uncomplete a task."
            return self._toggle_complete(data, index, False, date)

        elif action == "remove":
            if index is None:
                return "Error: index is required to remove a task."
            return self._remove_item(data, index, date)

        elif action == "list":
            return self._format_list(data, "daily", date)

        elif action == "clear":
            completed = [i for i, item in enumerate(data["items"]) if item["completed"]]
            if not completed:
                return "No completed items to clear."
            data["items"] = [item for item in data["items"] if not item["completed"]]
            self._save_daily(data, date)
            return f"Cleared {len(completed)} completed items."

        elif action == "move":
            if index is None or not target_list:
                return "Error: index and target_list are required to move a task."
            return self._move_item(data, index, target_list, date)

        elif action == "show_stats":
            return self._get_stats(data, "daily", date)

        return f"Unknown action: {action}"

    def _handle_global(
        self,
        action: str,
        content: str | None,
        priority: str | None,
        index: int | None,
        target_list: str | None,
    ) -> str:
        data = self._load_global()

        if action == "add":
            if not content:
                return "Error: content is required to add a task."
            item = {
                "id": len(data["items"]) + 1,
                "content": content,
                "completed": False,
                "priority": priority or "medium",
                "created_at": self._now().isoformat(),
            }
            data["items"].append(item)
            self._save_global(data)
            return f"Added to global todo: [{item['id']}] {content} (priority: {item['priority']})"

        elif action == "complete":
            if index is None:
                return "Error: index is required to complete a task."
            return self._toggle_complete_global(data, index, True)

        elif action == "uncomplete":
            if index is None:
                return "Error: index is required to uncomplete a task."
            return self._toggle_complete_global(data, index, False)

        elif action == "remove":
            if index is None:
                return "Error: index is required to remove a task."
            return self._remove_item_global(data, index)

        elif action == "list":
            return self._format_list(data, "global")

        elif action == "clear":
            completed = [i for i, item in enumerate(data["items"]) if item["completed"]]
            if not completed:
                return "No completed items to clear."
            data["items"] = [item for item in data["items"] if not item["completed"]]
            self._save_global(data)
            return f"Cleared {len(completed)} completed items."

        elif action == "move":
            if index is None or not target_list:
                return "Error: index and target_list are required to move a task."
            return self._move_item_global(data, index, target_list)

        elif action == "show_stats":
            return self._get_stats_global(data)

        return f"Unknown action: {action}"

    def _toggle_complete(self, data: dict, index: int, completed: bool, date: str | None) -> str:
        items = data["items"]
        if index < 0 or index >= len(items):
            return f"Invalid index {index}. Valid range: 0-{len(items) - 1}."

        item = items[index]

        if completed and not item.get("completed"):
            self._record_completed(item, "daily", date)

        items[index]["completed"] = completed
        items[index]["completed_at"] = self._now().isoformat() if completed else None
        self._save_daily(data, date)
        status = "completed" if completed else "uncompleted"
        return f"Task [{index}] '{items[index]['content']}' marked as {status}."

    def _toggle_complete_global(self, data: dict, index: int, completed: bool) -> str:
        items = data["items"]
        if index < 0 or index >= len(items):
            return f"Invalid index {index}. Valid range: 0-{len(items) - 1}."

        item = items[index]

        if completed and not item.get("completed"):
            self._record_completed(item, "global")

        items[index]["completed"] = completed
        items[index]["completed_at"] = self._now().isoformat() if completed else None
        self._save_global(data)
        status = "completed" if completed else "uncompleted"
        return f"Task [{index}] '{items[index]['content']}' marked as {status}."

    def _remove_item(self, data: dict, index: int, date: str | None) -> str:
        items = data["items"]
        if index < 0 or index >= len(items):
            return f"Invalid index {index}. Valid range: 0-{len(items) - 1}."
        removed = items.pop(index)
        self._save_daily(data, date)
        return f"Removed: [{index}] {removed['content']}"

    def _remove_item_global(self, data: dict, index: int) -> str:
        items = data["items"]
        if index < 0 or index >= len(items):
            return f"Invalid index {index}. Valid range: 0-{len(items) - 1}."
        removed = items.pop(index)
        self._save_global(data)
        return f"Removed: [{index}] {removed['content']}"

    def _move_item(self, data: dict, index: int, target_list: str, date: str | None) -> str:
        items = data["items"]
        if index < 0 or index >= len(items):
            return f"Invalid index {index}. Valid range: 0-{len(items) - 1}."

        item = items.pop(index)
        self._save_daily(data, date)

        if target_list == "global":
            target_data = self._load_global()
            item["id"] = len(target_data["items"]) + 1
            target_data["items"].append(item)
            self._save_global(target_data)
            return f"Moved to global: {item['content']}"
        elif target_list == "daily":
            target_data = self._load_daily(date)
            item["id"] = len(target_data["items"]) + 1
            target_data["items"].append(item)
            self._save_daily(target_data, date)
            return f"Moved to daily: {item['content']}"

        return f"Invalid target_list: {target_list}. Use 'daily' or 'global'."

    def _move_item_global(self, data: dict, index: int, target_list: str) -> str:
        items = data["items"]
        if index < 0 or index >= len(items):
            return f"Invalid index {index}. Valid range: 0-{len(items) - 1}."

        item = items.pop(index)
        self._save_global(data)

        if target_list == "daily":
            target_data = self._load_daily(None)
            item["id"] = len(target_data["items"]) + 1
            target_data["items"].append(item)
            self._save_daily(target_data, None)
            return f"Moved to daily: {item['content']}"
        elif target_list == "global":
            target_data = self._load_global()
            item["id"] = len(target_data["items"]) + 1
            target_data["items"].append(item)
            self._save_global(target_data)
            return f"Moved to global: {item['content']}"

        return f"Invalid target_list: {target_list}. Use 'daily' or 'global'."

    def _format_list(self, data: dict, list_type: str, date: str | None = None) -> str:
        items = data["items"]

        if not items:
            display_date = date or self._today_str()
            list_name = f"Daily ({display_date})" if list_type == "daily" else "Global"
            return f"No tasks in {list_name}."

        completed = [i for i, item in enumerate(items) if item["completed"]]
        pending = [i for i, item in enumerate(items) if not item["completed"]]

        display_date = date or self._today_str()
        list_name = f"Daily ({display_date})" if list_type == "daily" else "Global"

        lines = [f"## {list_name}", ""]

        if pending:
            lines.append("### Pending:")
            for i in pending:
                item = items[i]
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    item.get("priority", "medium"), "🟡"
                )
                lines.append(f"  [{i}] {priority_emoji} {item['content']}")

        if completed:
            lines.append("")
            lines.append("### Completed:")
            for i in completed:
                item = items[i]
                lines.append(f"  [{i}] ✅ {item['content']}")

        lines.append("")
        lines.append(f"Total: {len(items)} | Pending: {len(pending)} | Completed: {len(completed)}")

        return "\n".join(lines)

    def _get_stats(self, data: dict, list_type: str, date: str | None = None) -> str:
        items = data["items"]
        completed = [i for i, item in enumerate(items) if item["completed"]]
        pending = [i for i, item in enumerate(items) if not item["completed"]]

        priority_counts = {"high": 0, "medium": 0, "low": 0}
        for item in items:
            p = item.get("priority", "medium")
            priority_counts[p] = priority_counts.get(p, 0) + 1

        display_date = date or self._today_str()
        list_name = f"Daily ({display_date})" if list_type == "daily" else "Global"

        lines = [f"### {list_name} Stats:", ""]
        lines.append(f"  Total tasks: {len(items)}")
        lines.append(f"  Pending: {len(pending)}")
        lines.append(f"  Completed: {len(completed)}")

        if len(items) > 0:
            pct = round(len(completed) / len(items) * 100)
            lines.append(f"  Progress: {pct}%")

        lines.append("")
        lines.append("  By priority:")
        lines.append(f"    🔴 High: {priority_counts.get('high', 0)}")
        lines.append(f"    🟡 Medium: {priority_counts.get('medium', 0)}")
        lines.append(f"    🟢 Low: {priority_counts.get('low', 0)}")

        return "\n".join(lines)

    def _get_stats_global(self, data: dict) -> str:
        return self._get_stats(data, "global")

    def _get_history(
        self,
        history_date: str | None = None,
        history_month: str | None = None,
        limit: int | None = None,
    ) -> str:
        history = self._load_history()
        limit = limit or 20

        if history_date:
            items = history.get("by_date", {}).get(history_date, [])
            return self._format_history(items, f"Completed on {history_date}")

        if history_month:
            items = history.get("by_month", {}).get(history_month, [])
            month_name = history_month
            return self._format_history(items, f"Completed in {month_name}")

        items = history.get("completed", [])[:limit]
        return self._format_history(items, f"Recent Completions (last {len(items)})")

    def _format_history(self, items: list[dict], title: str) -> str:
        if not items:
            return f"{title}: No completed tasks."

        lines = [f"## {title}", ""]

        for item in items:
            completed_at = item.get("completed_at", "unknown")
            date_str = completed_at[:10] if completed_at else "unknown"
            time_str = completed_at[11:16] if completed_at else ""
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                item.get("priority", "medium"), "🟡"
            )
            list_type = item.get("list_type", "daily")
            lines.append(
                f"  {priority_emoji} [{list_type}] {item['content']} ({date_str} {time_str})"
            )

        lines.append("")
        lines.append(f"Total: {len(items)} items")

        return "\n".join(lines)

    def _log_done(self, content: str | None, notes: str | None) -> str:
        if not content:
            return "Error: content is required for log_done."

        history = self._load_history()

        completed_item = {
            "content": content,
            "completed_at": self._now().isoformat(),
            "list_type": "log_done",
            "priority": "medium",
            "notes": notes or "",
        }

        history["completed"].insert(0, completed_item)
        history["completed"] = history["completed"][:1000]

        today = self._today_str()
        if today not in history["by_date"]:
            history["by_date"][today] = []
        history["by_date"][today].append(completed_item)

        month_key = today[:7]
        if month_key not in history["by_month"]:
            history["by_month"][month_key] = []
        history["by_month"][month_key].append(completed_item)

        self._save_history(history)

        msg = f"Logged: {content}"
        if notes:
            msg += f"\n  Notes: {notes}"

        return msg
