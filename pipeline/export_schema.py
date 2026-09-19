"""Export JSON Schemas of the published data files (input for TypeScript type generation)."""

import json
from pathlib import Path

from pydantic import TypeAdapter

from mappetito_pipeline.models import Ingredient, Recipe

SCHEMA_DIR = Path(__file__).parent / "schema"


def main() -> None:
    SCHEMA_DIR.mkdir(exist_ok=True)
    schemas = {
        "ingredients.schema.json": TypeAdapter(list[Ingredient]).json_schema(),
        "recipes.schema.json": TypeAdapter(list[Recipe]).json_schema(),
    }
    for name, schema in schemas.items():
        (SCHEMA_DIR / name).write_text(json.dumps(schema, indent=2) + "\n")
        print(f"wrote {SCHEMA_DIR / name}")


if __name__ == "__main__":
    main()
