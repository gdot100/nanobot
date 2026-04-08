---
name: todo
description: Track and manage daily and global todo lists with history tracking.
always: true
---

# Todo Tracking

You have access to a two-list todo system to help track what the user wants to accomplish:

## Lists

- **Daily list** — Tasks for the current day. Automatically resets each day (separate file per date).
- **Global list** — Long-term tasks that persist across days. Use for goals, projects, recurring items.

## History Tracking

All completed tasks are automatically recorded in history. You can view:
- Recent completions
- By specific date
- By month

Use this to remind the user of what they've accomplished!

## When to Use This System

1. **Proactive tracking**: When the user mentions tasks, goals, or things they need to do, proactively offer to add them to the appropriate list.
2. **Daily check-ins**: At the start of each conversation or day, offer to show the current daily and global todo lists.
3. **Completion follow-up**: When user completes a task they mentioned, mark it as complete.
4. **Guidance**: Help them break down larger goals into actionable daily tasks.
5. **Show progress**: Periodically show history to remind them of accomplishments.

## Usage

Use the `todo_list` tool with these parameters:

- `action`: add, complete, uncomplete, remove, list, clear, move, show_stats, history, log_done
- `list_type`: "daily" or "global"
- `content`: task description (for add)
- `priority`: "low", "medium", or "high" (for add)
- `index`: task index (for complete/uncomplete/remove/move)
- `date`: YYYY-MM-DD for daily list (defaults to today)
- `target_list`: "daily" or "global" (for move)
- `history_date`: YYYY-MM-DD for history lookup
- `history_month`: YYYY-MM for monthly history
- `limit`: number of history items (default 20)
- `notes`: notes about what was done (for log_done)

### Examples

```python
# Show today's daily list
todo_list(action="list", list_type="daily")

# Show global list
todo_list(action="list", list_type="global")

# Add a daily task
todo_list(action="add", list_type="daily", content="Review PR #123", priority="high")

# Add a global task
todo_list(action="add", list_type="global", content="Learn Spanish", priority="medium")

# Mark task complete
todo_list(action="complete", list_type="daily", index=0)

# Show stats
todo_list(action="show_stats", list_type="daily")

# View recent history
todo_list(action="history")

# View history for specific date
todo_list(action="history", history_date="2026-04-08")

# View history for specific month
todo_list(action="history", history_month="2026-04")

# Log work done without a todo (e.g., user just mentions completing something)
todo_list(action="log_done", content="Fixed the login bug", notes="Changed password reset flow")
```

## Best Practices

- Ask about priorities when adding tasks (high/medium/low)
- Break large goals into smaller daily tasks
- Move completed items to trash regularly with `clear`
- Use `show_stats` to give the user a sense of progress
- Be proactive: don't wait for the user to ask, offer to track things
- Use `log_done` when user mentions completing something that wasn't on the list
- Show history periodically to remind user of their accomplishments
