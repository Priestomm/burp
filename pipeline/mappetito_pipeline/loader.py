"""Reads curated JSON data files and validates them with the Pydantic models."""

from pathlib import Path

from pydantic import TypeAdapter

from mappetito_pipeline.models import Ingredient, RecipeDraft

SEED_DIR = Path(__file__).parent.parent / "data" / "seed"


def load_ingredients(path: Path = SEED_DIR / "ingredients.json") -> dict[str, Ingredient]:
    items = TypeAdapter(list[Ingredient]).validate_json(path.read_text())
    by_id: dict[str, Ingredient] = {}
    for item in items:
        if item.id in by_id:
            raise ValueError(f"duplicate ingredient id '{item.id}'")
        by_id[item.id] = item
    return by_id


def load_recipe_drafts(path: Path = SEED_DIR / "recipes.json") -> list[RecipeDraft]:
    return TypeAdapter(list[RecipeDraft]).validate_json(path.read_text())
