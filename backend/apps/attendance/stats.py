def attendance_percentage(present: int, late: int, absent: int) -> float | None:
    """(present + late) / (present + late + absent). Leave days are excused and excluded from the denominator.
    None when there is nothing to measure."""
    counted = present + late + absent
    return None if counted == 0 else round((present + late) * 100 / counted, 2)
