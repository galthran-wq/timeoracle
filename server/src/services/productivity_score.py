DEPTH_WEIGHTS = {"deep": 1.0, "shallow": 0.6, "reactive": 0.3}


def compute_productivity_score(focus_score: float | None, depth: str | None) -> float | None:
    if focus_score is None or depth is None:
        return None
    weight = DEPTH_WEIGHTS.get(depth, 0.4)
    return round(focus_score * weight * 100, 1)
