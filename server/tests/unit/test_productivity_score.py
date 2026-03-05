from src.services.productivity_score import compute_productivity_score


class TestComputeProductivityScore:
    def test_deep_high_focus(self):
        assert compute_productivity_score(0.95, "deep") == 95.0

    def test_deep_moderate_focus(self):
        assert compute_productivity_score(0.6, "deep") == 60.0

    def test_shallow_focused(self):
        assert compute_productivity_score(0.8, "shallow") == 48.0

    def test_reactive_high_engagement(self):
        assert compute_productivity_score(0.9, "reactive") == 27.0

    def test_shallow_scattered(self):
        assert compute_productivity_score(0.3, "shallow") == 18.0

    def test_none_focus(self):
        assert compute_productivity_score(None, "deep") is None

    def test_none_depth(self):
        assert compute_productivity_score(0.8, None) is None

    def test_both_none(self):
        assert compute_productivity_score(None, None) is None

    def test_unknown_depth_uses_default_weight(self):
        assert compute_productivity_score(1.0, "unknown") == 40.0
