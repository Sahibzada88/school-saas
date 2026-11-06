"""Pure grading/ranking helpers (no database), so the rules are easy to test."""
from decimal import ROUND_HALF_UP, Decimal

TWO = Decimal("0.01")


def q2(value) -> Decimal:
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def percentage(obtained, total) -> Decimal:
    total = Decimal(total)
    return Decimal("0.00") if total == 0 else q2(Decimal(obtained) * 100 / total)


def band_for(percent, bands):
    """bands: iterable of objects with min_percent/max_percent. The highest band whose minimum is <= percent wins,
    so small gaps between bands (e.g. 89.99 -> 90) never leave a student ungraded."""
    candidates = [b for b in bands if Decimal(b.min_percent) <= Decimal(percent)]
    return max(candidates, key=lambda b: Decimal(b.min_percent)) if candidates else None


def rank_desc(scores: dict) -> dict:
    """Competition ranking (1, 2, 2, 4): equal scores share a position."""
    values = list(scores.values())
    return {key: 1 + sum(1 for other in values if other > score) for key, score in scores.items()}


def validate_bands(bands: list[dict]) -> list[str]:
    """Returns error messages: ranges must be valid and must not overlap."""
    errors = []
    ordered = sorted(bands, key=lambda b: Decimal(b["min_percent"]))
    for band in ordered:
        if Decimal(band["min_percent"]) > Decimal(band["max_percent"]):
            errors.append(f"Grade {band['grade']}: minimum is above the maximum.")
        if Decimal(band["min_percent"]) < 0 or Decimal(band["max_percent"]) > 100:
            errors.append(f"Grade {band['grade']}: percentages must be between 0 and 100.")
    for previous, current in zip(ordered, ordered[1:]):
        if Decimal(current["min_percent"]) <= Decimal(previous["max_percent"]):
            errors.append(f"Grades {previous['grade']} and {current['grade']} overlap.")
    return errors
