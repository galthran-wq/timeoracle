---
name: digitalgulag
description: Scan digitalgulag activity sessions and create/update labeled timeline entries
requires:
  env:
    - DIGITALGULAG_API_URL
    - DIGITALGULAG_TOKEN
  bins:
    - curl
    - jq
---

# digitalgulag Timeline Labeling

You analyze computer activity sessions from a personal time tracker and produce
labeled timeline entries. Each entry represents a meaningful block of time with
a human-readable label, category, and color.

## Authentication

All API requests require:
```
Authorization: Bearer $DIGITALGULAG_TOKEN
```
Base URL: `$DIGITALGULAG_API_URL`

## Workflow

### Step 1: Fetch today's activity sessions

```bash
curl -s "$DIGITALGULAG_API_URL/api/activity/sessions?date=$(date +%Y-%m-%d)&range=day&limit=1000" \
  -H "Authorization: Bearer $DIGITALGULAG_TOKEN" | jq .
```

Each session has: `app_name`, `window_title`, `window_titles[]`, `url`, `start_time`, `end_time`.

Focus on sessions from the last 2 hours (to cover any late-arriving data from the previous run).

### Step 2: Fetch existing timeline entries

```bash
curl -s "$DIGITALGULAG_API_URL/api/timeline?date=$(date +%Y-%m-%d)&range=day&limit=500" \
  -H "Authorization: Bearer $DIGITALGULAG_TOKEN" | jq .
```

Important:
- Entries with `edited_by_user: true` must NEVER be overwritten or conflicted with.
- Entries with `edited_by_user: false` and `source: "ai_generated"` can be updated by including their `id`.
- Do not create new entries that overlap with user-edited entries.

### Step 3: Analyze and label

For each activity session or cluster of related sessions:

1. **Group** sessions by similarity (same app, similar window titles, same URL domain) and time proximity (gaps < 5 minutes).
2. **Label** each group with a concise, human-readable description of the activity.
   - Good: "Code review on digitalgulag PR #42", "Reading HN thread on AI agents"
   - Bad: "VS Code", "Firefox usage", "Computer activity"
3. **Categorize** using one of: Work, Communication, Research, Entertainment, Health, Personal, Admin.
4. **Color** based on category (see mapping below).
5. **Confidence** (0.0-1.0): how certain you are about the label. Use 0.9+ for obvious activities (coding in IDE with clear project), 0.5-0.7 for ambiguous ones.
6. **Source summary**: one sentence explaining your reasoning.

If an existing AI-generated entry covers the same time window, include its `id` to update it instead of creating a duplicate.

### Step 4: Submit

```bash
curl -s -X POST "$DIGITALGULAG_API_URL/api/timeline/bulk" \
  -H "Authorization: Bearer $DIGITALGULAG_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "entries": [
      {
        "date": "2026-01-15",
        "start_time": "2026-01-15T10:00:00+00:00",
        "end_time": "2026-01-15T11:30:00+00:00",
        "label": "Coding: digitalgulag daemon refactor",
        "description": "Refactoring capture module in Rust daemon",
        "category": "Work",
        "color": "#3B82F6",
        "source_summary": "VS Code with digitalgulag project, editing daemon/src/capture/*.rs files",
        "confidence": 0.92
      }
    ]
  }' | jq .
```

To update an existing entry, include `"id": "existing-uuid-here"` in the item.

Response: `{ "created": N, "updated": N, "skipped": N, "errors": [...] }`
- `skipped` = entries the user manually edited (protected from AI overwrite)
- `errors` = entries with invalid IDs

### Step 5: Report

Print a brief summary:
- How many sessions were processed
- How many timeline entries were created/updated/skipped
- Any notable patterns (e.g., "Most time spent on: Work (4h)")

## Category Color Mapping

| Category       | Color     |
|---------------|-----------|
| Work          | `#3B82F6` |
| Communication | `#8B5CF6` |
| Research      | `#10B981` |
| Entertainment | `#F59E0B` |
| Health        | `#EF4444` |
| Personal      | `#EC4899` |
| Admin         | `#6B7280` |

## Rules

- All timestamps must be timezone-aware (include UTC offset like `+00:00`)
- `date` field must match the date portion of `start_time`
- `end_time` must be after `start_time`
- `label` max 255 characters
- `category` max 100 characters
- `color` must be hex format like `#3B82F6`
- Maximum 100 entries per bulk request
