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
