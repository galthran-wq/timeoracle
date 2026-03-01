from datetime import date

from src.agent.prompts import CATEGORIES, build_system_prompt


class TestBuildSystemPrompt:
    def test_contains_all_categories(self):
        prompt = build_system_prompt()
        for cat in CATEGORIES:
            assert cat in prompt

    def test_contains_all_colors(self):
        prompt = build_system_prompt()
        for color in CATEGORIES.values():
            assert color in prompt

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
