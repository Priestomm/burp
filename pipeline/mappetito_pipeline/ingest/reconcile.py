"""Reconcile: turn an LLM `ExtractedRecipe` into the app's own `RecipeDraft`.

The LLM's opinion is only ever checked, never trusted blindly: ingredients are resolved on
the canonical catalog, the country becomes ISO 3166-1 numeric, and the diet is computed from
the ingredients (the LLM's declared diet is a cross-check). Anything doubtful makes the
recipe `needs_review` instead of being papered over.
"""

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

import pycountry

from mappetito_pipeline.diet import (
    NonVegetarianIngredientError,
    UnknownIngredientError,
    compute_diet,
)
from mappetito_pipeline.ingest.store import ImportedRecipe, Provenance
from mappetito_pipeline.ingest.structure import ExtractedIngredient, ExtractedRecipe
from mappetito_pipeline.matching import SynonymIndex, normalize_name
from mappetito_pipeline.models import Adaptation, Diet, Ingredient, RecipeDraft, RecipeIngredient


@dataclass
class _Line:
    item: RecipeIngredient
    resolved: bool  # False when the id is only a slug of the name, not in the catalog
    name: str  # normalized canonical_name as written by the model, to match substitutions


MIN_CONFIDENCE = 0.6
_DIET_RANK = {"vegan": 0, "vegetarian": 1, "neither": 2}


def country_numeric(iso2: str) -> str | None:
    """ISO 3166-1 alpha-2 -> zero-padded numeric code (the app's `country_code`)."""
    try:
        country = pycountry.countries.get(alpha_2=iso2.strip().upper())
    except LookupError:
        return None
    return country.numeric if country else None


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "recipe"


def reconcile(
    extracted: ExtractedRecipe,
    ingredients: Mapping[str, Ingredient],
    provenance: Provenance | None = None,
) -> ImportedRecipe:
    index = SynonymIndex(ingredients)
    issues: list[str] = []
    provenance = provenance or Provenance(source="manual")

    if extracted.origin.confidence < MIN_CONFIDENCE:
        issues.append(
            f"country confidence {extracted.origin.confidence:.2f} < {MIN_CONFIDENCE}: "
            f"{extracted.origin.reasoning}"
        )

    code = country_numeric(extracted.origin.country_iso2)
    if code is None:
        issues.append(f"unknown country code '{extracted.origin.country_iso2}'")

    lines = [_to_line(i, index, ingredients) for i in extracted.ingredients]
    adaptation = None
    if extracted.diet == "neither":
        lines, adaptation = _veganize(extracted, lines, index, issues)

    for line in lines:
        if not line.resolved:
            issues.append(f"unresolved ingredient '{line.item.ingredient_id}'")

    draft = None
    diet: Diet | None = None
    if code is not None:
        draft = RecipeDraft(
            id=f"{extracted.origin.country_iso2.lower()}-{slugify(extracted.title)}",
            name=extracted.title,
            name_it=extracted.title,
            country_code=code,
            servings=extracted.servings or 1,
            ingredients=[line.item for line in lines],
            steps=extracted.steps,
            adaptation=adaptation,
            source=extracted.source_url or "instagram",
            license="user-shared",
        )
        diet = _computed_diet(draft, ingredients, extracted.diet, issues)

    recipe_id = draft.id if draft else f"xx-{slugify(extracted.title)}"
    return ImportedRecipe(
        id=recipe_id,
        status="needs_review" if issues or draft is None else "ready",
        issues=issues,
        diet=diet,
        draft=draft,
        extracted=extracted,
        provenance=provenance,
    )


def _to_line(
    raw: ExtractedIngredient, index: SynonymIndex, ingredients: Mapping[str, Ingredient]
) -> _Line:
    if raw.canonical_name in ingredients:
        resolved = raw.canonical_name
    else:
        resolved = index.resolve(raw.canonical_name, raw.original_text)
    quantity = raw.quantity if raw.quantity and raw.quantity > 0 else None
    item = RecipeIngredient(
        ingredient_id=resolved or slugify(raw.canonical_name).replace("-", "_"),
        quantity=quantity,
        unit=raw.unit if quantity else None,
        # "to taste" items are seasoning; everything with a quantity defines the dish.
        is_core=quantity is not None,
    )
    return _Line(item, resolved is not None, normalize_name(raw.canonical_name))


def _veganize(
    extracted: ExtractedRecipe,
    lines: list[_Line],
    index: SynonymIndex,
    issues: list[str],
) -> tuple[list[_Line], Adaptation | None]:
    """Apply the proposed substitutions so a meat/fish dish becomes a publishable variant."""
    version = extracted.veganized_version
    if version is None or not version.substitutions:
        issues.append("dish is not vegetarian and no substitutions were proposed")
        return lines, None

    result = list(lines)
    for sub in version.substitutions:
        target_id = index.resolve(sub.original)
        target_name = normalize_name(sub.original)
        replacement_id = index.resolve(sub.replacement)
        for position, line in enumerate(result):
            if line.item.ingredient_id != target_id and line.name != target_name:
                continue
            new_id = replacement_id or slugify(sub.replacement).replace("-", "_")
            result[position] = _Line(
                line.item.model_copy(update={"ingredient_id": new_id}),
                replacement_id is not None,
                line.name,
            )
            break
        else:
            issues.append(f"substitution target '{sub.original}' not found in the ingredients")

    changes = "; ".join(f"{s.original} -> {s.replacement}" for s in version.substitutions)
    if version.notes:
        changes += f". {version.notes}"
    return result, Adaptation(original_dish=extracted.title, changes=changes)


def _computed_diet(
    draft: RecipeDraft,
    ingredients: Mapping[str, Ingredient],
    declared: str,
    issues: list[str],
) -> Diet | None:
    try:
        computed = compute_diet(draft, ingredients)
    except UnknownIngredientError:
        return None  # already reported as unresolved ingredient(s)
    except NonVegetarianIngredientError as error:
        issues.append(str(error))
        return None
    if declared != "neither" and _DIET_RANK[computed] > _DIET_RANK[declared]:
        issues.append(f"model declared '{declared}' but the ingredients make it '{computed}'")
    return computed
