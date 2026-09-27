"""The whole import: post -> content -> structured recipe.

Shared by the CLI and the Telegram bot so both behave the same.
"""

import anthropic

from burp.catalog import SynonymIndex
from burp.extract import extract_content
from burp.frames import FrameDescriber
from burp.ingest import SourcePost
from burp.models import ImportedRecipe
from burp.structure import structure_recipe
from burp.transcribe import Transcriber

DIET_LABELS = {
    "vegan": "vegana",
    "vegetarian": "vegetariana",
    "neither": "né vegana né vegetariana",
}


def import_post(
    post: SourcePost,
    catalog: SynonymIndex,
    client: anthropic.Anthropic,
    model: str,
    transcriber: Transcriber | None = None,
    describer: FrameDescriber | None = None,
) -> ImportedRecipe:
    content = extract_content(post, transcriber, describer)
    recipe = structure_recipe(
        content.text, catalog, client, model, source_url=post.url, author_handle=post.author_handle
    )
    return ImportedRecipe(
        recipe=recipe, content_source=content.source, content_reason=content.reason
    )


def summarize(imported: ImportedRecipe) -> str:
    """Short human-readable outcome, used by the CLI and the bot."""
    recipe = imported.recipe
    lines = [recipe.title]
    if recipe.author_handle:
        lines.append(f"di @{recipe.author_handle}")
    tags = [recipe.tags.cuisine, recipe.tags.course, DIET_LABELS[recipe.tags.diet]]
    lines.append(" · ".join(t for t in tags if t))
    lines.append(f"{len(recipe.ingredients)} ingredienti, {len(recipe.steps)} passaggi")
    if recipe.completeness.status == "complete":
        lines.append("completa")
    else:
        lines.append("parziale, manca: " + "; ".join(recipe.completeness.missing))
    lines.append(f"fonte: {imported.content_source}")
    return "\n".join(lines)
