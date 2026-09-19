"""TheMealDB source (stub).

TODO: implement `fetch_meals`. TheMealDB provides recipes with ingredient lists and
steps, but its data is community-contributed: check its terms/license before
publishing anything derived from it, and map its free-text ingredients to canonical
ingredient ids.
"""

from dataclasses import dataclass, field


@dataclass
class TheMealDbMeal:
    id: str
    name: str
    area: str  # e.g. "Italian"; TODO: map to ISO 3166-1 numeric country codes
    ingredients: list[tuple[str, str]] = field(default_factory=list)  # (name, measure)
    instructions: str = ""


def fetch_meals(area: str) -> list[TheMealDbMeal]:
    """Return the meals of a given area (cuisine)."""
    raise NotImplementedError("TODO: TheMealDB source is not implemented yet")
