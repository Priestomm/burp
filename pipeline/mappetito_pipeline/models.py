"""Pydantic models: the single source of truth for the data schema.

The JSON Schema exported from these models (see export_schema.py) is used to
generate the TypeScript types consumed by the app.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Diet = Literal["vegan", "vegetarian"]


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


class RecipeIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str
    quantity: float | None = Field(default=None, gt=0, description="None means 'to taste'")
    unit: str | None = None
    is_core: bool = Field(description="True if the dish is not the same without it")


class Adaptation(BaseModel):
    """Set when a vegetarian dish is a variant of a traditionally meat or fish dish."""

    model_config = ConfigDict(extra="forbid")

    original_dish: str
    changes: str


class RecipeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str
    name_it: str
    country_code: str = Field(
        pattern=r"^\d{3}$",
        description="ISO 3166-1 numeric, zero-padded; matches world-atlas feature ids",
    )
    servings: int = Field(default=1, ge=1)
    ingredients: list[RecipeIngredient] = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    adaptation: Adaptation | None = Field(
        default=None, description="None for traditionally vegetarian/vegan dishes"
    )
    source: str
    license: str


class RecipeDraft(RecipeBase):
    """A recipe as written in curated data. It must NOT declare `diet`: it is computed."""


class Recipe(RecipeBase):
    """A recipe as published to the app, with `diet` computed from its ingredients."""

    diet: Diet
