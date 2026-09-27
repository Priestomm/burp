"""The whole import: post -> content -> structured recipe -> reconciled, storable recipe.

Shared by the CLI and the Telegram bot so both behave the same.
"""

from collections.abc import Mapping

import anthropic

from burp.extract import extract_content
from burp.frames import FrameDescriber
from burp.ingest import SourcePost
from burp.models import Ingredient
from burp.reconcile import reconcile
from burp.store import ImportedRecipe, Provenance
from burp.structure import structure_recipe
from burp.transcribe import Transcriber


def import_post(
    post: SourcePost,
    ingredients: Mapping[str, Ingredient],
    client: anthropic.Anthropic,
    model: str,
    transcriber: Transcriber | None = None,
    describer: FrameDescriber | None = None,
) -> ImportedRecipe:
    content = extract_content(post, transcriber, describer)
    extracted = structure_recipe(content.text, ingredients, client, model, source_url=post.url)
    return reconcile(
        extracted, ingredients, Provenance(source=content.source, reason=content.reason)
    )


def summarize(recipe: ImportedRecipe) -> str:
    """Short human-readable outcome, used by the CLI and the bot."""
    draft = recipe.draft
    lines = [f"{recipe.extracted.title} ({recipe.id})"]
    if draft:
        lines.append(f"paese {recipe.extracted.origin.country_iso2} ({draft.country_code})")
    lines.append(f"dieta: {recipe.diet or 'da verificare'}")
    if recipe.draft and recipe.draft.adaptation:
        lines.append(f"veganizzata: {recipe.draft.adaptation.changes}")
    lines.append(f"fonte: {recipe.provenance.source}")
    if recipe.status == "ready":
        lines.append("stato: ready, comparirà sulla mappa al prossimo build")
    else:
        lines.append("stato: needs_review")
        lines += [f"- {issue}" for issue in recipe.issues]
    return "\n".join(lines)
