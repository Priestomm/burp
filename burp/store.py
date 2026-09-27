"""Persistence of imported recipes: one JSON file per recipe under `data/imported/`."""

import re
import unicodedata
from pathlib import Path

from burp.models import ImportedRecipe

IMPORTED_DIR = Path(__file__).parent.parent / "data" / "imported"


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "recipe"


def save(imported: ImportedRecipe, directory: Path = IMPORTED_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slugify(imported.recipe.title)}.json"
    path.write_text(imported.model_dump_json(indent=2) + "\n")
    return path


def load_all(directory: Path = IMPORTED_DIR) -> list[ImportedRecipe]:
    if not directory.exists():
        return []
    return [
        ImportedRecipe.model_validate_json(path.read_text())
        for path in sorted(directory.glob("*.json"))
    ]
