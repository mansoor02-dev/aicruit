"""
Helper / utility functions.
"""


def scale_to_ten(score: float, original_max: float = 5.0) -> float:
    """Scale a score from its original range to a 0–10 range, rounded to 1 dp."""
    return round((score / original_max) * 10, 1)


def clamp(value: float, lo: float = 0.0, hi: float = 10.0) -> float:
    """Clamp a value between lo and hi."""
    return max(lo, min(hi, value))
