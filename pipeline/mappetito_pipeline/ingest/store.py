"""Persistence of imported recipes: one JSON file per recipe under `data/imported/`.

A recipe is `ready` (published by build.py) or `needs_review` (kept for a human to fix and
flip to `ready`). The raw extraction and its provenance are stored with it.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mappetito_pipeline.ingest.structure import ExtractedRecipe
from mappetito_pipeline.models import Diet, RecipeDraft

IMPORTED_DIR = Path(__file__).parent.parent.parent / "data" / "imported"

Status = Literal["ready", "needs_review"]


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["caption", "transcript", "frames", "manual"]
    reason: str = ""


class ImportedRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: Status
    issues: list[str]
    diet: Diet | None = None
    draft: RecipeDraft | None
    extracted: ExtractedRecipe
    provenance: Provenance


def save(recipe: ImportedRecipe, directory: Path = IMPORTED_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{recipe.id}.json"
    path.write_text(recipe.model_dump_json(indent=2) + "\n")
    return path


def load_all(directory: Path = IMPORTED_DIR) -> list[ImportedRecipe]:
    if not directory.exists():
        return []
    return [
        ImportedRecipe.model_validate_json(path.read_text())
        for path in sorted(directory.glob("*.json"))
    ]


def ready_drafts(directory: Path = IMPORTED_DIR) -> list[RecipeDraft]:
    return [r.draft for r in load_all(directory) if r.status == "ready" and r.draft is not None]
