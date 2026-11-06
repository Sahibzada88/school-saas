from django.db import transaction


def next_number(school, key: str) -> int:
    """Gap-free-ish per-school counter (student numbers, invoices, receipts, employee ids). Row-locked, race safe."""
    from apps.tenants.models import NumberSequence

    with transaction.atomic():
        sequence, _ = NumberSequence.objects.select_for_update().get_or_create(
            school=school, key=key, defaults={"next_value": 1}
        )
        value = sequence.next_value
        sequence.next_value = value + 1
        sequence.save(update_fields=["next_value", "updated_at"])
    return value


def format_number(prefix: str, value: int, width: int = 5) -> str:
    return f"{prefix}-{value:0{width}d}"


def reserve_numbers(school, key: str, count: int) -> int:
    """Reserve `count` consecutive numbers with ONE row lock (bulk invoice generation). Returns the first number."""
    from apps.tenants.models import NumberSequence

    with transaction.atomic():
        sequence, _ = NumberSequence.objects.select_for_update().get_or_create(school=school, key=key, defaults={"next_value": 1})
        start = sequence.next_value
        sequence.next_value = start + count
        sequence.save(update_fields=["next_value", "updated_at"])
    return start
