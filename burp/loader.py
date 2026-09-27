"""Reads the canonical ingredient catalog and validates it with the Pydantic models."""

from pathlib import Path

from pydantic import TypeAdapter

from burp.models import Ingredient

SEED_DIR = Path(__file__).parent.parent / "data" / "seed"


def load_ingredients(path: Path = SEED_DIR / "ingredients.json") -> dict[str, Ingredient]:
    items = TypeAdapter(list[Ingredient]).validate_json(path.read_text())
    by_id: dict[str, Ingredient] = {}
    for item in items:
        if item.id in by_id:
            raise ValueError(f"duplicate ingredient id '{item.id}'")
        by_id[item.id] = item
    return by_id
