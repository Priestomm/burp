"""The canonical ingredient catalog: Italian names, synonyms and diet flags.

It gives every recipe the same name for the same ingredient ("tomato", "pomodori" and
"pomodoro" all become "pomodoro"), which is what makes search by ingredient work, and it
knows hidden animal ingredients (pecorino, fish sauce...) to cross-check the model's diet.
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from burp.models import Diet

CATALOG_PATH = Path(__file__).parent.parent / "data" / "ingredients.json"

_NON_WORD = re.compile(r"[^a-z0-9]+")
_DIET_RANK: dict[Diet, int] = {"vegan": 0, "vegetarian": 1, "neither": 2}


class Ingredient(BaseModel):
    """A canonical ingredient with names and synonyms in Italian and English."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$", description="Canonical snake_case id")
    name_en: str
    name_it: str
    synonyms_en: list[str] = Field(default_factory=list)
    synonyms_it: list[str] = Field(default_factory=list)
    is_vegetarian: bool
    is_vegan: bool
    shelf_life_days: int | None = Field(default=None, gt=0)
    notes: str | None = Field(
        default=None, description="Explains hidden animal origin or other caveats"
    )

    @model_validator(mode="after")
    def _vegan_implies_vegetarian(self) -> "Ingredient":
        if self.is_vegan and not self.is_vegetarian:
            raise ValueError(f"{self.id}: an ingredient cannot be vegan but not vegetarian")
        return self

    @property
    def canonical_name(self) -> str:
        return self.name_it.lower()

    @property
    def diet(self) -> Diet:
        return "vegan" if self.is_vegan else "vegetarian" if self.is_vegetarian else "neither"


def load_ingredients(path: Path = CATALOG_PATH) -> dict[str, Ingredient]:
    items = TypeAdapter(list[Ingredient]).validate_json(path.read_text())
    by_id: dict[str, Ingredient] = {}
    for item in items:
        if item.id in by_id:
            raise ValueError(f"duplicate ingredient id '{item.id}'")
        by_id[item.id] = item
    return by_id


def normalize_name(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NON_WORD.sub(" ", stripped).strip()


class SynonymIndex:
    """Canonical id, `name_en` and `name_it` are registered first; a synonym only if that
    normalized name is not already claimed."""

    def __init__(self, ingredients: Mapping[str, Ingredient]) -> None:
        self.ingredients = ingredients
        self._by_name: dict[str, str] = {}
        for item in ingredients.values():
            for name in (item.id.replace("_", " "), item.name_en, item.name_it):
                self._by_name.setdefault(normalize_name(name), item.id)
        for item in ingredients.values():
            for name in (*item.synonyms_en, *item.synonyms_it):
                self._by_name.setdefault(normalize_name(name), item.id)

    def resolve(self, *candidates: str) -> str | None:
        """Exact match on each candidate in order, then the longest known name inside one."""
        normalized = [normalize_name(c) for c in candidates if c]
        for name in normalized:
            if name in self._by_name:
                return self._by_name[name]
        for name in normalized:
            padded = f" {name} "
            hits = [key for key in self._by_name if key and f" {key} " in padded]
            if hits:
                return self._by_name[max(hits, key=len)]
        return None

    def lookup(self, name: str) -> Ingredient | None:
        """Exact match only: "pasta sfoglia" must not become "pasta"."""
        found = self._by_name.get(normalize_name(name))
        return self.ingredients[found] if found else None

    def canonical_name(self, name: str) -> str:
        """The catalog's Italian name when the ingredient is known, else the name normalized."""
        item = self.lookup(name)
        return item.canonical_name if item else " ".join(name.lower().split())

    def diet_floor(self, names: Iterable[str]) -> Diet:
        """The least strict diet the known ingredients allow. Unknown names count as vegan, so
        this can only prove that a recipe is *not* vegan or vegetarian, never that it is."""
        diets = [item.diet for name in names if (item := self.lookup(name))]
        return max(diets, key=_DIET_RANK.__getitem__, default="vegan")


def stricter_than(declared: Diet, floor: Diet) -> bool:
    """True when `declared` claims more than the ingredients allow (e.g. vegan with pecorino)."""
    return _DIET_RANK[declared] < _DIET_RANK[floor]
