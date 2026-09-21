"""Structuring: free text from a post -> a validated `ExtractedRecipe` via the Anthropic API.

This model follows what the LLM can reasonably produce (free-text ingredients, ISO 3166-1
alpha-2 country, a confidence, a declared diet). `reconcile.py` turns it into the app's own
`RecipeDraft`, where the diet is computed and countries are numeric.
"""

import logging
from collections.abc import Mapping
from typing import Literal, Self

import anthropic
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from mappetito_pipeline.models import Ingredient

log = logging.getLogger(__name__)

Diet3 = Literal["vegan", "vegetarian", "neither"]


class ExtractedIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_name: str = Field(description="Id from the ingredient catalog when one fits")
    original_text: str = Field(description="The ingredient line as written in the post")
    quantity: float | None = Field(default=None, description="null when 'to taste' or missing")
    unit: str | None = None


class Origin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_iso2: str = Field(description="ISO 3166-1 alpha-2, uppercase, e.g. IT")
    cuisine: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class Substitution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original: str = Field(description="Non-vegan ingredient, as a catalog id when one fits")
    replacement: str = Field(description="Vegan replacement, as a catalog id when one fits")


class VeganizedVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    substitutions: list[Substitution]
    notes: str | None = None


class ExtractedRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    source_url: str | None = None
    servings: int | None = None
    time_minutes: int | None = None
    ingredients: list[ExtractedIngredient] = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    origin: Origin
    diet: Diet3
    veganized_version: VeganizedVersion | None = Field(
        default=None, description="Required unless diet is 'vegan', null otherwise"
    )

    @model_validator(mode="after")
    def _veganized_version_iff_not_vegan(self) -> Self:
        if self.diet == "vegan" and self.veganized_version is not None:
            raise ValueError("veganized_version must be null when diet is 'vegan'")
        if self.diet != "vegan" and self.veganized_version is None:
            raise ValueError("veganized_version is required when diet is not 'vegan'")
        return self


class StructuringError(RuntimeError):
    """The model never returned a valid recipe within the allowed attempts."""


SYSTEM_PROMPT = """\
You turn the text of a cooking post (caption, transcript or on-screen text) into one \
structured recipe for Mappetito, an app of vegetarian and vegan dishes placed on a world map.

Rules:
- Use only what the text says. Never invent ingredients, quantities or steps.
- ingredients[].canonical_name: use an id from the catalog below when the ingredient fits \
one (also through its synonyms, in any language). If none fits, use a short lowercase English \
snake_case name. Always keep the line as written in original_text.
- diet: "vegan", "vegetarian" (eggs or dairy, no meat/fish) or "neither". Watch for hidden \
animal ingredients: guanciale, pancetta, parmigiano/pecorino (animal rennet), fish sauce, \
anchovies, bonito/dashi, gelatin, lard, meat or fish broth, Worcestershire sauce.
- veganized_version: null if and only if diet is "vegan". Otherwise list the substitutions \
that make the dish vegan (original -> replacement, both catalog ids when possible).
- origin.country_iso2: the country the dish comes from, from the dish itself and not from the \
account posting it. Be honest in origin.confidence (0 to 1): use below 0.6 when the origin is \
ambiguous, fusion, or you are guessing, and explain in origin.reasoning. A low confidence is \
better than a confident wrong country.
- Keep steps concise, in the language of the post."""


def _catalog_text(ingredients: Mapping[str, Ingredient]) -> str:
    lines = []
    for item in ingredients.values():
        names = ", ".join([item.name_en, item.name_it, *item.synonyms_en, *item.synonyms_it])
        flag = "vegan" if item.is_vegan else "vegetarian" if item.is_vegetarian else "animal"
        lines.append(f"{item.id} [{flag}]: {names}")
    return "Ingredient catalog (id [diet]: names):\n" + "\n".join(lines)


def structure_recipe(
    text: str,
    ingredients: Mapping[str, Ingredient],
    client: anthropic.Anthropic,
    model: str,
    source_url: str | None = None,
    max_attempts: int = 2,
) -> ExtractedRecipe:
    """Ask the model for a recipe, validating the output and retrying once on invalid JSON."""
    # The system prompt and catalog are identical across calls, so they are cached.
    system = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT + "\n\n" + _catalog_text(ingredients),
            "cache_control": {"type": "ephemeral"},
        }
    ]
    prompt = f"Post text:\n\n{text}"
    error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        content = prompt
        if error is not None:
            content += (
                f"\n\nYour previous answer was rejected: {error}\n"
                "Return a corrected recipe that satisfies the schema and the rules."
            )
        try:
            response = client.messages.parse(
                model=model,
                max_tokens=8000,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_format=ExtractedRecipe,
            )
        except (ValidationError, anthropic.BadRequestError) as caught:
            error = caught
            log.warning("structuring attempt %d/%d invalid: %s", attempt, max_attempts, caught)
            continue
        recipe = response.parsed_output
        if recipe is None:
            error = ValueError(f"no parsable output (stop_reason={response.stop_reason})")
            log.warning("structuring attempt %d/%d empty: %s", attempt, max_attempts, error)
            continue
        return recipe.model_copy(update={"source_url": source_url or recipe.source_url})
    raise StructuringError(f"no valid recipe after {max_attempts} attempts: {error}")
