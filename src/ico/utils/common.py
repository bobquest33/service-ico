from decimal import Decimal


def quantize(value, divisibility):
    """
    Quantize the decimal value to the configured precision.
    """
    return value.quantize(Decimal(10) ** -divisibility)


def to_cents(amount: Decimal, divisibility: int) -> int:
    return int(amount * Decimal('10')**divisibility)


def from_cents(amount: int, divisibility: int) -> Decimal:
    return Decimal(amount) / Decimal('10')**divisibility