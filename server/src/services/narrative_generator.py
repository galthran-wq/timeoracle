import logging

from pydantic_ai import Agent

from src.core.config import settings

logger = logging.getLogger(__name__)

NARRATIVE_SYSTEM_PROMPT = """\
You are a personal productivity assistant. Given a user's day metrics and their top timeline entries, \
write a 2-3 sentence summary of what they accomplished and how their day went.

Rules:
- Address the user as "you"
- Be direct and conversational
- Describe patterns and what the user accomplished qualitatively
- Do not reference exact percentages, scores, or minute counts
- Focus on what stands out: deep work sessions, focus quality, fragmentation patterns, or attention shifts
- When deep work time is available, comment on how much sustained complex work happened
- When focus quality is notably high or low, mention it
- When the day was highly fragmented, note it as something to be aware of
"""

narrative_agent = Agent(system_prompt=NARRATIVE_SYSTEM_PROMPT)

ROLLING_NARRATIVE_SYSTEM_PROMPT = """\
You are a blunt, provocative personal productivity coach. Given a user's current day metrics and recent timeline entries, \
write a 2-3 sentence rolling commentary on their day SO FAR. This is not a retrospective — the day is still in progress.

Rules:
- Address the user as "you"
- Be direct, slightly confrontational, and honest — not cruel, but not sugarcoating
- React to the current state: are they working? idle? distracted? in a flow?
- If they haven't started working, call it out
- If they were productive but stopped, note the gap
- If they're in deep focus, encourage them to keep going
- If they keep switching between tasks, point it out
- Do not reference exact percentages, scores, or minute counts
- Keep it conversational and short — 2-3 sentences max
- Use present tense — describe what's happening now, not what happened
"""

rolling_narrative_agent = Agent(system_prompt=ROLLING_NARRATIVE_SYSTEM_PROMPT)


def _build_narrative_prompt(date_str: str, metrics: dict, timeline_entries: list[dict]) -> str:
    lines = [f"Date: {date_str}"]

    if metrics.get("category_breakdown"):
        lines.append("Category breakdown:")
        for item in metrics["category_breakdown"][:8]:
            lines.append(f"  - {item['category']}: {item['minutes']:.0f}min")

    if metrics.get("deep_work_minutes"):
        lines.append(f"Deep work: {metrics['deep_work_minutes']:.0f}min")
    if metrics.get("shallow_work_minutes"):
        lines.append(f"Shallow work: {metrics['shallow_work_minutes']:.0f}min")
    if metrics.get("reactive_minutes"):
        lines.append(f"Reactive (chat/notifications): {metrics['reactive_minutes']:.0f}min")
    if metrics.get("avg_focus_score") is not None:
        lines.append(f"Average focus quality: {metrics['avg_focus_score']:.0%}")
    if metrics.get("longest_focus_minutes"):
        lines.append(f"Longest focus streak: {metrics['longest_focus_minutes']:.0f}min")
    if metrics.get("fragmentation_index") is not None:
        lines.append(f"Fragmentation index: {metrics['fragmentation_index']:.1f}/10")
    if metrics.get("context_switches"):
        lines.append(f"Context switches: {metrics['context_switches']}")
    if metrics.get("focus_sessions_25min"):
        lines.append(f"Focus sessions (25min+): {metrics['focus_sessions_25min']}")
    if metrics.get("focus_sessions_90min"):
        lines.append(f"Focus sessions (90min+): {metrics['focus_sessions_90min']}")
    if metrics.get("productivity_score") is not None:
        lines.append(f"Productivity score: {metrics['productivity_score']:.0f}/100")
    if metrics.get("work_minutes"):
        lines.append(f"Work time: {metrics['work_minutes']:.0f}min")

    if timeline_entries:
        lines.append("Key timeline entries:")
        for e in timeline_entries[:15]:
            label = e.get("label", "")
            cat = e.get("category", "")
            lines.append(f"  - {label} [{cat}]")

    return "\n".join(lines)


def _build_rolling_prompt(
    current_time: str,
    metrics: dict,
    timeline_entries: list[dict],
) -> str:
    lines = [f"Current time: {current_time}"]

    work_minutes = metrics.get("work_minutes", 0)
    total_active = metrics.get("total_active_minutes", 0)
    if total_active == 0:
        lines.append("Status: No activity recorded yet today.")
    elif work_minutes == 0:
        lines.append(f"Status: Active for ~{total_active:.0f}min but no work detected.")
    else:
        lines.append(f"Status: ~{work_minutes:.0f}min of work so far, ~{total_active:.0f}min total active.")

    if metrics.get("deep_work_minutes"):
        lines.append(f"Deep work: ~{metrics['deep_work_minutes']:.0f}min")
    if metrics.get("avg_focus_score") is not None:
        lines.append(f"Focus quality so far: {metrics['avg_focus_score']:.0%}")
    if metrics.get("context_switches"):
        lines.append(f"Context switches: {metrics['context_switches']}")
    if metrics.get("fragmentation_index") is not None:
        lines.append(f"Fragmentation: {metrics['fragmentation_index']:.1f}/10")

    if timeline_entries:
        lines.append("Recent timeline (most recent first):")
        for e in timeline_entries[:10]:
            label = e.get("label", "")
            cat = e.get("category", "")
            start = e.get("start_time", "")
            end = e.get("end_time", "")
            lines.append(f"  - {label} [{cat}] {start}–{end}")

    return "\n".join(lines)


async def generate_rolling_narrative(
    current_time: str,
    metrics: dict,
    timeline_entries: list[dict],
    model: str | None = None,
) -> str:
    prompt = _build_rolling_prompt(current_time, metrics, timeline_entries)
    effective_model = model or settings.default_llm_model

    try:
        result = await rolling_narrative_agent.run(prompt, model=effective_model)
        return result.output
    except Exception:
        logger.exception("Failed to generate rolling narrative")
        return ""


async def generate_day_narrative(
    date_str: str,
    metrics: dict,
    timeline_entries: list[dict],
    model: str | None = None,
) -> str:
    prompt = _build_narrative_prompt(date_str, metrics, timeline_entries)
    effective_model = model or settings.default_llm_model

    try:
        result = await narrative_agent.run(prompt, model=effective_model)
        return result.output
    except Exception:
        logger.exception("Failed to generate narrative for %s", date_str)
        return ""
