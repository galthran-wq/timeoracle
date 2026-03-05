from src.services.category_utils import is_work_category


class TestIsWorkCategory:
    def test_none_category(self):
        assert is_work_category(None, None) is False

    def test_empty_string(self):
        assert is_work_category("", None) is False

    def test_work_explicit_true(self):
        cats = {"Coding": {"color": "#FF0000", "work": True}}
        assert is_work_category("Coding", cats) is True

    def test_work_explicit_false(self):
        cats = {"Gaming": {"color": "#FF0000", "work": False}}
        assert is_work_category("Gaming", cats) is False

    def test_default_non_work(self):
        assert is_work_category("Entertainment", None) is False
        assert is_work_category("Personal", None) is False
        assert is_work_category("Health", None) is False

    def test_default_work(self):
        assert is_work_category("Work", None) is True
        assert is_work_category("Communication", None) is True
        assert is_work_category("CustomCategory", None) is True

    def test_config_without_work_key(self):
        cats = {"Research": {"color": "#FF0000"}}
        assert is_work_category("Research", cats) is True

    def test_non_work_default_overridden_by_config(self):
        cats = {"Entertainment": {"color": "#FF0000", "work": True}}
        assert is_work_category("Entertainment", cats) is True
