"""burp! command line: import a recipe you share, then search your library.

    uv run burp import --url https://www.instagram.com/reel/XXXX/
    uv run burp import --caption-file caption.txt --url https://...
    uv run burp import --screenshot a.png b.png
    uv run burp search carbonara --tag primo --ingredient pecorino
    uv run burp show 3
    uv run burp bot

The manual inputs (--caption, --caption-file, --screenshot) always work, with no video download.
"""

import argparse
import logging
import sys
from pathlib import Path

import anthropic

from burp.catalog import SynonymIndex, load_ingredients
from burp.config import Settings, load_env
from burp.frames import ClaudeFrameDescriber
from burp.ingest import SourcePost, fetch_instagram, from_caption, from_screenshots
from burp.library import Library, SavedRecipe
from burp.pipeline import DIET_LABELS, import_post, summarize
from burp.transcribe import FasterWhisperTranscriber


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="burp", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("import", help="import one recipe you share")
    add.add_argument("--url", help="Instagram post/reel link (also recorded as the source)")
    add.add_argument("--caption", help="caption text, pasted")
    add.add_argument("--caption-file", type=Path, help="file with the caption text")
    add.add_argument("--screenshot", nargs="+", type=Path, help="screenshot(s) of the recipe")
    add.add_argument("--dry-run", action="store_true", help="print the result, do not save")

    search = commands.add_parser("search", help="search the library (no filter: list all)")
    search.add_argument("title", nargs="*", help="words in the title")
    search.add_argument("--tag", action="append", default=[], help="cuisine, course or diet")
    search.add_argument("--ingredient", action="append", default=[], help="an ingredient")

    show = commands.add_parser("show", help="print one recipe")
    show.add_argument("id", type=int)
    show.add_argument("--json", action="store_true", help="print the stored JSON")

    delete = commands.add_parser("delete", help="remove one recipe")
    delete.add_argument("id", type=int)

    commands.add_parser("bot", help="run the Telegram bot")

    args = parser.parse_args(argv)
    if args.command == "import" and not (
        args.url or args.caption or args.caption_file or args.screenshot
    ):
        add.error("give at least one of --url, --caption, --caption-file, --screenshot")
    return args


def build_post(args: argparse.Namespace, settings: Settings) -> SourcePost:
    caption = args.caption or (args.caption_file.read_text() if args.caption_file else "")
    if args.screenshot:
        return from_screenshots(args.screenshot, url=args.url, caption=caption)
    if caption:
        return from_caption(caption, url=args.url)
    return fetch_instagram(args.url, cookies_file=settings.instagram_cookies_file)


def main(
    argv: list[str] | None = None,
    *,
    client: anthropic.Anthropic | None = None,
    library: Library | None = None,
) -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    settings = Settings.from_env()
    if args.command == "bot":
        from burp.bot import main as bot_main

        return bot_main()

    catalog = SynonymIndex(load_ingredients())
    library = library or Library(settings.db_path, catalog)
    match args.command:
        case "import":
            return run_import(args, settings, catalog, library, client)
        case "search":
            results = library.search(" ".join(args.title), args.tag, args.ingredient)
            for saved in results:
                print(one_line(saved))
            if not results:
                print("nessuna ricetta trovata")
            return 0
        case "show":
            saved = library.get(args.id)
            if saved is None:
                print(f"no recipe #{args.id}", file=sys.stderr)
                return 1
            print(saved.imported.model_dump_json(indent=2) if args.json else full_text(saved))
            return 0
        case "delete":
            if not library.delete(args.id):
                print(f"no recipe #{args.id}", file=sys.stderr)
                return 1
            print(f"deleted #{args.id}")
            return 0
    return 2


def run_import(
    args: argparse.Namespace,
    settings: Settings,
    catalog: SynonymIndex,
    library: Library,
    client: anthropic.Anthropic | None,
) -> int:
    # Checked before downloading anything or calling the model: a duplicate costs nothing.
    if args.url and (existing := library.find_by_url(args.url)):
        print(f"già in libreria (#{existing.id}): {existing.recipe.title}")
        return 0
    if client is None:
        if not settings.anthropic_api_key:
            print("ANTHROPIC_API_KEY is not set (see .env.example)", file=sys.stderr)
            return 2
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        post = build_post(args, settings)
        imported = import_post(
            post,
            catalog,
            client,
            settings.model,
            transcriber=FasterWhisperTranscriber(settings.whisper_model),
            describer=ClaudeFrameDescriber(client, settings.model),
        )
    except RuntimeError as error:  # ingestion, content, structuring, missing extras
        print(f"import failed: {error}", file=sys.stderr)
        return 1

    print(summarize(imported))
    if args.dry_run:
        print("(dry run: nothing saved)")
    else:
        saved, created = library.add(imported)
        print(f"salvata come #{saved.id}" if created else f"già in libreria (#{saved.id})")
    return 0


def one_line(saved: SavedRecipe) -> str:
    recipe = saved.recipe
    tags = [recipe.tags.cuisine, recipe.tags.course, DIET_LABELS[recipe.tags.diet]]
    if recipe.completeness.status == "partial":
        tags.append("parziale")
    return f"#{saved.id:<4} {recipe.title}  ({', '.join(t for t in tags if t)})"


def full_text(saved: SavedRecipe) -> str:
    recipe = saved.recipe
    lines = [f"#{saved.id} {recipe.title}"]
    if recipe.author_handle:
        lines.append(f"di @{recipe.author_handle}")
    if recipe.source_url:
        lines.append(recipe.source_url)
    facts = []
    if recipe.servings:
        facts.append(f"{recipe.servings} porzioni")
    if recipe.time_minutes:
        facts.append(f"{recipe.time_minutes} minuti")
    tags = [recipe.tags.cuisine, recipe.tags.course, DIET_LABELS[recipe.tags.diet]]
    lines.append(" · ".join([*facts, *(t for t in tags if t)]))

    lines += ["", "Ingredienti:"]
    for item in recipe.ingredients:
        amount = (
            " ".join(part for part in (_number(item.quantity), item.unit) if part)
            or "quantità non indicata"
        )
        lines.append(f"- {item.canonical_name}: {amount}  [{item.original_text}]")
    lines += ["", "Procedimento:"]
    lines += [f"{n}. {step}" for n, step in enumerate(recipe.steps, 1)] or ["(non indicato)"]
    if recipe.completeness.status == "partial":
        lines += ["", "Ricetta parziale, manca: " + "; ".join(recipe.completeness.missing)]
    lines += ["", f"fonte del testo: {saved.imported.content_source}"]
    return "\n".join(lines)


def _number(value: float | None) -> str | None:
    if value is None:
        return None
    return str(int(value)) if value == int(value) else f"{value:g}"


if __name__ == "__main__":
    raise SystemExit(main())
