"""Pydantic models: the single source of truth for a recipe in the library.

`Recipe` is also the JSON schema the model must fill in (see structure.py), so every field
description here is part of the prompt.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Diet = Literal["vegan", "vegetarian", "neither"]
Course = Literal[
    "antipasto",
    "primo",
    "secondo",
    "contorno",
    "piatto unico",
    "dolce",
    "colazione",
    "snack",
    "bevanda",
    "salsa",
]
ContentSource = Literal["caption", "transcript", "frames"]


class RecipeIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_name: str = Field(
        description="Nome italiano, minuscolo, al singolare; quello del catalogo quando c'è"
    )
    original_text: str = Field(description="La riga dell'ingrediente come scritta nella fonte")
    quantity: float | None = Field(
        default=None, gt=0, description="null se q.b. o se la fonte non la dice"
    )
    unit: str | None = Field(default=None, description="In italiano: g, ml, cucchiaio, tazza...")


class Tags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cuisine: str | None = Field(default=None, description="In italiano, es. italiana, indiana")
    course: Course | None = None
    diet: Diet


class Completeness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["complete", "partial"]
    missing: list[str] = Field(
        default_factory=list,
        description="Cosa la fonte non dice, in italiano, es. 'quantità della pasta'",
    )

    @model_validator(mode="after")
    def _partial_iff_something_missing(self) -> Self:
        if self.status == "partial" and not self.missing:
            raise ValueError("a partial recipe must list what is missing")
        if self.status == "complete" and self.missing:
            raise ValueError("a recipe with missing items must be 'partial'")
        return self


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    source_url: str | None = None
    author_handle: str | None = Field(
        default=None, description="Username Instagram dell'autore, senza @; null se non noto"
    )
    servings: int | None = Field(default=None, ge=1)
    time_minutes: int | None = Field(default=None, ge=1)
    ingredients: list[RecipeIngredient] = Field(min_length=1)
    steps: list[str] = Field(default_factory=list, description="Vuoto se la fonte non li dice")
    tags: Tags
    completeness: Completeness


class ImportedRecipe(BaseModel):
    """A recipe as saved, with where its text came from."""

    model_config = ConfigDict(extra="forbid")

    recipe: Recipe
    content_source: ContentSource
    content_reason: str = Field(default="", description="Why cheaper sources were not enough")
