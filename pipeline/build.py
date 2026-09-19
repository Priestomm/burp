"""Build the dataset consumed by the app.

Reads curated data, validates it with Pydantic, computes each recipe's `diet`
and writes `recipes.json` and `ingredients.json` into `app/static/data/`.
"""

import json
import sys
from pathlib import Path

from pydantic import TypeAdapter

from mappetito_pipeline.diet import DietError, to_recipe
from mappetito_pipeline.loader import load_ingredients, load_recipe_drafts
from mappetito_pipeline.models import Ingredient, Recipe

OUTPUT_DIR = Path(__file__).parent.parent / "app" / "static" / "data"


def build(output_dir: Path = OUTPUT_DIR) -> tuple[list[Ingredient], list[Recipe]]:
    ingredients = load_ingredients()
    drafts = load_recipe_drafts()

    ids = [d.id for d in drafts]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate recipe ids: {sorted(duplicates)}")

    recipes = [to_recipe(draft, ingredients) for draft in drafts]

    output_dir.mkdir(parents=True, exist_ok=True)
    _write(output_dir / "ingredients.json", list[Ingredient], list(ingredients.values()))
    _write(output_dir / "recipes.json", list[Recipe], recipes)
    return list(ingredients.values()), recipes


def _write(path: Path, tp: type, data: object) -> None:
    payload = TypeAdapter(tp).dump_python(data, mode="json")
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    try:
        ingredients, recipes = build()
    except DietError as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1
    print(f"wrote {len(ingredients)} ingredients and {len(recipes)} recipes to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
