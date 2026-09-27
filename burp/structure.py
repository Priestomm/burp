"""Structuring: free text from a post -> a validated `Recipe` via the Anthropic API.

The model fills in the `Recipe` schema; its output is validated with Pydantic and retried once
if invalid. `finalize` then applies the rules that must not depend on the model's goodwill:
canonical names from the catalog, `partial` when quantities or steps are missing, and a diet
that is never more permissive than the known ingredients allow.
"""

import logging
import re

import anthropic
from pydantic import ValidationError

from burp.catalog import SynonymIndex, normalize_name, stricter_than
from burp.models import Completeness, Recipe, RecipeIngredient, Tags

log = logging.getLogger(__name__)

TO_TASTE = re.compile(
    r"\bq\.?\s?b\b|quanto basta|a piacere|a gusto|pizzic|to taste|as needed|a pinch|\bpinch",
    re.IGNORECASE,
)


class StructuringError(RuntimeError):
    """The model never returned a valid recipe within the allowed attempts."""


SYSTEM_PROMPT = """\
Trasformi il testo di un post di cucina (caption, trascrizione dell'audio o testo letto nei \
frame del video) in una ricetta strutturata per burp!, una libreria personale di ricette.

Regole:
- Usa solo quello che dice il testo. Non inventare mai ingredienti, quantità o passaggi.
- Scrivi tutto in italiano (title, steps, unit, canonical_name, cuisine, missing), traducendo \
se il post è in un'altra lingua. Solo original_text resta identico alla fonte.
- ingredients[].canonical_name: nome italiano, minuscolo, al singolare ("pomodoro", non \
"pomodori ramati"). Se l'ingrediente è nel catalogo qui sotto (anche tramite un sinonimo in \
qualunque lingua), usa esattamente il nome del catalogo.
- quantity: un numero (1/2 -> 0.5), null se la fonte non lo dice. Non stimare mai una quantità.
- unit: "q.b." (con quantity null) se la fonte dice q.b./a piacere/to taste, o per sale, pepe \
e condimenti simili elencati senza quantità. Per gli altri ingredienti senza quantità lascia \
unit null.
- steps: i passaggi della fonte, concisi. Lista vuota se la fonte non li descrive.
- servings e time_minutes: solo se la fonte li dice, altrimenti null.
- tags.diet: "vegan", "vegetarian" (uova o latticini, niente carne né pesce) o "neither". \
Attenzione agli ingredienti animali nascosti: guanciale, pancetta, parmigiano e pecorino \
(caglio animale), salsa di pesce, acciughe, dashi di bonito, gelatina, strutto, brodo di carne \
o di pesce, salsa Worcestershire.
- tags.course: la portata; null se non è chiara.
- completeness: "complete" solo se ogni ingrediente ha una quantità (o è q.b.) e ci sono i \
passaggi. Altrimenti "partial", con in missing cosa manca, es. "quantità della pasta", \
"procedimento".
- author_handle: solo se il testo dice esplicitamente di chi è la ricetta, senza @; \
altrimenti null. source_url: null."""


def _catalog_text(catalog: SynonymIndex) -> str:
    lines = []
    for item in catalog.ingredients.values():
        synonyms = ", ".join([item.name_en, *item.synonyms_it, *item.synonyms_en])
        lines.append(f"{item.canonical_name} [{item.diet}]: {synonyms}")
    return "Catalogo ingredienti (nome [dieta]: sinonimi):\n" + "\n".join(lines)


def structure_recipe(
    text: str,
    catalog: SynonymIndex,
    client: anthropic.Anthropic,
    model: str,
    source_url: str | None = None,
    author_handle: str | None = None,
    max_attempts: int = 2,
) -> Recipe:
    """Ask the model for a recipe, validating the output and retrying once if it is invalid."""
    # The system prompt and catalog are identical across calls, so they are cached.
    system = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT + "\n\n" + _catalog_text(catalog),
            "cache_control": {"type": "ephemeral"},
        }
    ]
    prompt = f"Testo del post:\n\n{text}"
    error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        content = prompt
        if error is not None:
            content += (
                f"\n\nLa tua risposta precedente è stata rifiutata: {error}\n"
                "Restituisci una ricetta corretta che rispetti lo schema e le regole."
            )
        try:
            response = client.messages.parse(
                model=model,
                max_tokens=8000,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_format=Recipe,
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
        return finalize(recipe, catalog, source_url, author_handle)
    raise StructuringError(f"no valid recipe after {max_attempts} attempts: {error}")


def finalize(
    recipe: Recipe,
    catalog: SynonymIndex,
    source_url: str | None = None,
    author_handle: str | None = None,
) -> Recipe:
    """Deterministic rules applied on top of the model's answer."""
    ingredients = [
        item.model_copy(update={"canonical_name": catalog.canonical_name(item.canonical_name)})
        for item in recipe.ingredients
    ]
    handle = author_handle or recipe.author_handle
    return recipe.model_copy(
        update={
            "source_url": source_url,
            "author_handle": handle.lstrip("@") if handle else None,
            "ingredients": ingredients,
            "tags": _checked_diet(recipe, catalog, [i.canonical_name for i in ingredients]),
            "completeness": _checked_completeness(recipe, ingredients),
        }
    )


def _checked_completeness(recipe: Recipe, ingredients: list[RecipeIngredient]) -> Completeness:
    missing = list(recipe.completeness.missing)
    mentioned = f" {normalize_name(' '.join(missing))} "
    for item in ingredients:
        to_taste = item.unit == "q.b." or TO_TASTE.search(item.original_text)
        listed = f" {normalize_name(item.canonical_name)} " in mentioned
        if item.quantity is None and not to_taste and not listed:
            missing.append(f"quantità di {item.canonical_name}")
    if not recipe.steps and " procedimento " not in mentioned:
        missing.append("procedimento")
    if missing != recipe.completeness.missing:
        log.info("completeness: marked partial, missing %s", missing)
    return Completeness(status="partial" if missing else "complete", missing=missing)


def _checked_diet(recipe: Recipe, catalog: SynonymIndex, names: list[str]) -> Tags:
    floor = catalog.diet_floor(names)
    if not stricter_than(recipe.tags.diet, floor):
        return recipe.tags
    log.warning("diet: model said '%s' but the ingredients make it '%s'", recipe.tags.diet, floor)
    return recipe.tags.model_copy(update={"diet": floor})
