from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP


PRICE_SCALE = Decimal("0.01")
MONEY_SCALE = Decimal("0.01")


def to_decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_price(value: Decimal | int | float | str) -> Decimal:
    return to_decimal(value).quantize(PRICE_SCALE, rounding=ROUND_HALF_UP)


def round_money(value: Decimal | int | float | str) -> Decimal:
    return to_decimal(value).quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)


def round_quantity(value: Decimal | int | float | str, precision: int = 0, rounding: str = ROUND_DOWN) -> Decimal:
    scale = Decimal("1") if precision <= 0 else Decimal("1").scaleb(-precision)
    return to_decimal(value).quantize(scale, rounding=rounding)
