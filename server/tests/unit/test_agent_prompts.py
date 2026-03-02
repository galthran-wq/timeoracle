from datetime import date

from src.agent.prompts import DEFAULT_CATEGORIES, build_system_prompt


class TestBuildSystemPrompt:
    def test_contains_all_default_categories(self):
        prompt = build_system_prompt()
        for cat in DEFAULT_CATEGORIES:
            assert cat in prompt

    def test_contains_all_default_colors(self):
        prompt = build_system_prompt()
        for cfg in DEFAULT_CATEGORIES.values():
            assert cfg["color"] in prompt

    def test_contains_category_types(self):
        prompt = build_system_prompt()
        assert "productive" in prompt
        assert "distraction" in prompt
        assert "neutral" in prompt

    def test_no_date_context_when_none(self):
        prompt = build_system_prompt(None)
        assert "Today's date context" not in prompt

    def test_includes_date_context(self):
        prompt = build_system_prompt(date(2026, 3, 1))
        assert "2026-03-01" in prompt
        assert "Sunday" in prompt

    def test_includes_workflow_steps(self):
        prompt = build_system_prompt()
        assert "get_activity_sessions" in prompt
        assert "get_existing_timeline" in prompt
        assert "save_timeline_entries" in prompt

    def test_includes_labeling_rules(self):
        prompt = build_system_prompt()
        assert "edited_by_user" in prompt
        assert "overlapping" in prompt
        assert "confidence" in prompt

    def test_custom_categories(self):
        custom = {
            "Coding": {"color": "#FF0000", "type": "productive"},
            "Meetings": {"color": "#00FF00", "type": "neutral"},
        }
        prompt = build_system_prompt(categories=custom)
        assert "Coding" in prompt
        assert "#FF0000" in prompt
        assert "Meetings" in prompt
        assert "Work" not in prompt

    def test_classification_rules_injected(self):
        rules = ["VS Code is always Work", "YouTube is Entertainment"]
        prompt = build_system_prompt(classification_rules=rules)
        assert "VS Code is always Work" in prompt
        assert "YouTube is Entertainment" in prompt
        assert "User classification rules" in prompt
        assert "take priority" in prompt

    def test_no_rules_section_when_empty(self):
        prompt = build_system_prompt(classification_rules=None)
        assert "User classification rules" not in prompt

    def test_memories_injected(self):
        memories = [
            "Figma should be Work, not Personal",
            "Terminal with docker-compose is DevOps",
        ]
        prompt = build_system_prompt(memories=memories)
        assert "Figma should be Work, not Personal" in prompt
        assert "Terminal with docker-compose is DevOps" in prompt
        assert "Learned corrections" in prompt

    def test_no_memories_section_when_empty(self):
        prompt = build_system_prompt(memories=None)
        assert "Learned corrections" not in prompt

    def test_save_memory_mentioned_in_chat_mode(self):
        prompt = build_system_prompt()
        assert "save_memory" in prompt

    def test_day_boundary_context(self):
        prompt = build_system_prompt(
            target_date=date(2026, 3, 1),
            day_start_hour=5,
            day_timezone="America/New_York",
        )
        assert "5:00 America/New_York" in prompt
        assert "previous logical day" in prompt
