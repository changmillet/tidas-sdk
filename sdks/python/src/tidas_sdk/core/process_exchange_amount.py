"""Exact decimal comparison for Process inventory amounts validated as TIDAS Real strings."""

from decimal import Decimal

from pydantic import ValidationInfo
from pydantic_core import PydanticCustomError


def _decimal_parts(value: str) -> tuple[str, int]:
    mantissa, _, exponent = value.lower().partition("e")
    if not mantissa.isascii():
        # Python's Real pattern also accepts Unicode decimal digits.
        mantissa = "".join(str(int(c)) if c.isdecimal() else c for c in mantissa)
    integer, _, fraction = mantissa.lstrip("+-").partition(".")
    digits = (integer + fraction).lstrip("0")
    if not digits:
        return "0", 0
    coefficient = digits.rstrip("0")
    # Decimal accepts an arbitrary-length exponent token as an integer coefficient.
    scale = int(Decimal(exponent or "0")) + len(digits) - len(coefficient) - len(fraction)
    return ("-" if mantissa.startswith("-") else "") + coefficient, scale


def exchange_amount_error(mean: str, result: str, variable: str | None) -> PydanticCustomError | None:
    if (variable or "").strip() or _decimal_parts(mean) == _decimal_parts(result):
        return None
    return PydanticCustomError(
        "process_exchange_amount_conflict",
        "Without a variable, resultingAmount ({resultingAmount}) must equal meanAmount ({meanAmount}).",
        {"meanAmount": mean, "resultingAmount": result},
    )


def validate_resulting_amount(value: str, info: ValidationInfo) -> str:
    mean = info.data.get("mean_amount")
    if mean is not None:
        error = exchange_amount_error(mean, value, info.data.get("reference_to_variable"))
        if error:
            raise error
    return value
