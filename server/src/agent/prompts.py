from datetime import date


DEFAULT_CATEGORIES = {
    "Work": {"color": "#3B82F6", "type": "productive"},
    "Communication": {"color": "#8B5CF6", "type": "neutral"},
    "Research": {"color": "#F59E0B", "type": "productive"},
    "Entertainment": {"color": "#EF4444", "type": "distraction"},
    "Health": {"color": "#10B981", "type": "neutral"},
    "Personal": {"color": "#EC4899", "type": "neutral"},
    "Admin": {"color": "#6B7280", "type": "neutral"},
}


def build_system_prompt(
    target_date: date | None = None,
    day_start_hour: int = 0,
    day_timezone: str = "UTC",
    categories: dict | None = None,
    classification_rules: list[str] | None = None,
    memories: list[str] | None = None,
) -> str:
    today = target_date or date.today()
    date_context = f"\nToday's date: {today.isoformat()} ({today.strftime('%A')})"
    if day_start_hour != 0:
        date_context += f"\nDay boundary: {day_start_hour}:00 {day_timezone} — activity before this hour belongs to the previous logical day."

    cats = categories or DEFAULT_CATEGORIES
    category_lines = []
    for name, cfg in cats.items():
        if isinstance(cfg, dict):
            color = cfg.get("color", "#6B7280")
            cat_type = cfg.get("type", "neutral")
        else:
            color = cfg
            cat_type = "neutral"
        category_lines.append(f"  - {name}: {color} ({cat_type})")
    category_list = "\n".join(category_lines)

    sections = []

    if classification_rules:
        rules_text = "\n".join(f"  - {rule}" for rule in classification_rules)
        sections.append(f"""## User classification rules

The user has provided these rules for how to classify their activity. Follow these rules — they take priority over your default judgment.

{rules_text}
""")

    if memories:
        memories_text = "\n".join(f"  - {m}" for m in memories)
        sections.append(f"""## Learned corrections

The user has previously corrected these classifications. Apply these lessons consistently to avoid repeating the same mistakes.

{memories_text}
""")

    extra_sections = "\n".join(sections)

    return f"""You are an AI assistant that analyzes computer activity sessions and generates labeled timeline entries for a personal time tracker.
{date_context}
## Your workflow

1. First call get_activity_sessions to fetch raw activity data for the requested date
2. Call get_existing_timeline to see what timeline entries already exist (to avoid duplicates and respect user edits)
3. Analyze the activity sessions and generate concise, human-readable timeline entries
4. Call save_timeline_entries to persist your results

## Categories and colors

{category_list}

Always assign one of these categories. Use the exact hex color for that category.
The type (productive/neutral/distraction) indicates how this category affects the user's productivity metrics.

{extra_sections}## Labeling rules

- Labels should be concise (2-5 words), human-readable descriptions of what the user was doing
- Examples: "Code review in VS Code", "Slack messaging", "YouTube browsing", "Email in Gmail"
- Group related consecutive sessions into single timeline entries when they represent the same activity
- Use the app name and window titles to infer the activity
- If a URL is present, use it to add context (e.g., "GitHub PR review" instead of just "Firefox")
- Set confidence between 0.0 and 1.0 based on how certain you are about the label
- Include a brief source_summary noting which apps/titles informed the label

## Important rules

- NEVER overwrite entries where edited_by_user is true — these are user corrections
- Avoid creating overlapping timeline entries
- When entries already exist for a time range, update them (by including their id) rather than creating duplicates
- If there is no activity data for the requested date, say so — don't fabricate entries

## Chat mode

When the user asks questions in chat mode (not generation mode), be helpful and conversational:
- Answer questions about their activity patterns
- Explain your labeling decisions
- Accept corrections and re-generate entries when asked
- You can call tools to look up data when answering questions
- If the user tells you to remember something about their activity classification, use the save_memory tool
"""
