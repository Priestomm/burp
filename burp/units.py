"""Units as the model writes them (Italian, free text) -> a base unit that can be scaled.

Grams and millilitres stay as they are, spoons are counted in teaspoons (1 cucchiaio = 3
cucchiaini) and a quantity without a unit counts pieces. Anything else ("lattina da 15 oz",
"mazzetto") is not scalable and is shown as written.
"""

from typing import Literal

from burp.catalog import normalize_name

BaseUnit = Literal["g", "ml", "tsp", "piece"]

# normalized unit -> (base unit, how many base units one of it is)
UNITS: dict[str, tuple[BaseUnit, float]] = {
    **dict.fromkeys(["g", "gr", "grammo", "grammi"], ("g", 1)),
    **dict.fromkeys(["kg", "chilo", "chili", "chilogrammo", "chilogrammi"], ("g", 1000)),
    **dict.fromkeys(["ml", "millilitro", "millilitri"], ("ml", 1)),
    "cl": ("ml", 10),
    "dl": ("ml", 100),
    **dict.fromkeys(["l", "lt", "litro", "litri"], ("ml", 1000)),
    # A recipe "tazza" is almost always a translated US cup.
    **dict.fromkeys(["tazza", "tazze"], ("ml", 240)),
    **dict.fromkeys(["cucchiaio", "cucchiai"], ("tsp", 3)),
    **dict.fromkeys(["cucchiaino", "cucchiaini"], ("tsp", 1)),
    **dict.fromkeys(
        ["pezzo", "pezzi", "spicchio", "spicchi", "fetta", "fette", "foglia", "foglie"],
        ("piece", 1),
    ),
}


def to_base(quantity: float | None, unit: str | None) -> tuple[BaseUnit, float] | None:
    """(base unit, quantity in it), or None when the amount cannot be scaled."""
    if quantity is None:
        return None
    if unit is None or not unit.strip():
        return "piece", quantity
    found = UNITS.get(normalize_name(unit))
    if found is None:
        return None
    base, factor = found
    return base, quantity * factor
