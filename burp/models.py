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


class CuisineWord(BaseModel):
    """A word in the language of the dish's cuisine, for the Zine page (e.g. もちもち)."""

    model_config = ConfigDict(extra="forbid")

    lingua: str = Field(description="Codice BCP 47 della lingua, es. ja, ko, zh, th, ar, hi")
    parola: str = Field(description="La parola o espressione breve, nel suo alfabeto")
    traduzione: str = Field(description="Cosa vuol dire, in italiano, poche parole")


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    nome_riga_1: str = Field(
        description="Prima parte del nome del piatto, senza aggettivi, es. 'Gnocchi'"
    )
    nome_riga_2: str | None = Field(
        default=None, description="Seconda parte del nome, es. 'di tofu'; null se il nome è breve"
    )
    descrittore: str | None = Field(
        default=None,
        description="Gli aggettivi tolti dal nome, minuscoli, es. 'gommosi e glassati'; null se "
        "non ce ne sono",
    )
    parola_cucina: CuisineWord | None = Field(
        default=None,
        description="Solo per cucine con alfabeto non latino e se sei sicuro; altrimenti null",
    )
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


class IngredientEdit(BaseModel):
    """What the user changed on one ingredient. The model's answer itself is never modified."""

    model_config = ConfigDict(extra="forbid")

    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    by_eye: bool = False  # "Sì, a occhio": the user accepts not knowing the quantity


class Estimate(BaseModel):
    """A quantity the AI guessed because the post did not say it."""

    model_config = ConfigDict(extra="forbid")

    quantity: float = Field(gt=0)
    unit: str | None = None
    reason: str = Field(description="Why this amount, in a few words")


class Enrichment(BaseModel):
    """What "Completa con l'AI" added. Kept apart: the post's own text is never replaced, and
    the user's edits always win over it."""

    model_config = ConfigDict(extra="forbid")

    model: str
    created_at: str
    quantities: dict[int, Estimate] = Field(default_factory=dict)
    servings: int | None = Field(default=None, ge=1)
    time_minutes: int | None = Field(default=None, ge=1)
    steps: list[str] = Field(default_factory=list, description="The steps, rewritten")
    steps_note: str | None = Field(
        default=None, description="What was added to the steps beyond the post, if anything"
    )
    # "Togli le stime" hides them and keeps them: showing them again costs no new call.
    active: bool = True


class ImportedRecipe(BaseModel):
    """A recipe as saved, with where its text came from and what the user changed."""

    model_config = ConfigDict(extra="forbid")

    recipe: Recipe
    content_source: ContentSource
    content_reason: str = Field(default="", description="Why cheaper sources were not enough")
    edits: dict[int, IngredientEdit] = Field(
        default_factory=dict, description="User changes, by ingredient position"
    )
    enrichment: Enrichment | None = None

    @property
    def shown_enrichment(self) -> Enrichment | None:
        """The AI's additions, if the user has them on."""
        return self.enrichment if self.enrichment and self.enrichment.active else None

    def without_enrichment(self) -> "ImportedRecipe":
        """The post plus the user's edits: what a new estimate starts from."""
        return self.model_copy(update={"enrichment": None})
