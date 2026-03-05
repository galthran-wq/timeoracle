NON_WORK_DEFAULTS = {"Entertainment", "Personal", "Health"}


def is_work_category(category: str | None, categories_config: dict | None) -> bool:
    if not category:
        return False
    cats = categories_config or {}
    cfg = cats.get(category, {})
    if isinstance(cfg, dict) and "work" in cfg:
        return cfg["work"]
    return category not in NON_WORK_DEFAULTS
