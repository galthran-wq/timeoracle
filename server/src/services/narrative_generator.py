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
- Focus on what stands out: productive streaks, distractions, variety of work, or lack of activity
"""

narrative_agent = Agent(system_prompt=NARRATIVE_SYSTEM_PROMPT)


def _build_narrative_prompt(date_str: str, metrics: dict, timeline_entries: list[dict]) -> str:
    lines = [f"Date: {date_str}"]

    if metrics.get("category_breakdown"):
        lines.append("Category breakdown:")
        for item in metrics["category_breakdown"][:8]:
            lines.append(f"  - {item['category']} ({item['type']}): {item['minutes']:.0f}min")

    if metrics.get("longest_focus_minutes"):
        lines.append(f"Longest focus streak: {metrics['longest_focus_minutes']:.0f}min")
    if metrics.get("context_switches"):
        lines.append(f"Context switches: {metrics['context_switches']}")

    if timeline_entries:
        lines.append("Key timeline entries:")
        for e in timeline_entries[:15]:
            label = e.get("label", "")
            cat = e.get("category", "")
            lines.append(f"  - {label} [{cat}]")

    return "\n".join(lines)


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
