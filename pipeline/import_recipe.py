"""Import one recipe from an Instagram post the user shares, or from pasted text/screenshots.

    uv run python import_recipe.py --url https://www.instagram.com/reel/XXXX/
    uv run python import_recipe.py --caption-file caption.txt --url https://...
    uv run python import_recipe.py --screenshot a.png b.png

The manual inputs (--caption, --caption-file, --screenshot) always work, with no video download.
"""

import argparse
import logging
import sys
from pathlib import Path

import anthropic

from mappetito_pipeline.config import Settings, load_env
from mappetito_pipeline.ingest.frames import ClaudeFrameDescriber
from mappetito_pipeline.ingest.pipeline import import_post, summarize
from mappetito_pipeline.ingest.sources import (
    SourcePost,
    fetch_instagram,
    from_caption,
    from_screenshots,
)
from mappetito_pipeline.ingest.store import IMPORTED_DIR, save
from mappetito_pipeline.ingest.transcribe import FasterWhisperTranscriber
from mappetito_pipeline.loader import load_ingredients


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url", help="Instagram post/reel link (also recorded as the source)")
    parser.add_argument("--caption", help="caption text, pasted")
    parser.add_argument("--caption-file", type=Path, help="file with the caption text")
    parser.add_argument("--screenshot", nargs="+", type=Path, help="screenshot(s) of the recipe")
    parser.add_argument("--dry-run", action="store_true", help="print the result, do not save")
    args = parser.parse_args(argv)
    if not (args.url or args.caption or args.caption_file or args.screenshot):
        parser.error("give at least one of --url, --caption, --caption-file, --screenshot")
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
    output_dir: Path = IMPORTED_DIR,
) -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    settings = Settings.from_env()
    if client is None:
        if not settings.anthropic_api_key:
            print("ANTHROPIC_API_KEY is not set (see .env.example)", file=sys.stderr)
            return 2
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        post = build_post(args, settings)
        recipe = import_post(
            post,
            load_ingredients(),
            client,
            settings.model,
            transcriber=FasterWhisperTranscriber(settings.whisper_model),
            describer=ClaudeFrameDescriber(client, settings.model),
        )
    except RuntimeError as error:  # ingestion, content, structuring, missing extras
        print(f"import failed: {error}", file=sys.stderr)
        return 1

    print(summarize(recipe))
    if args.dry_run:
        print("(dry run: nothing saved)")
    else:
        print(f"saved {save(recipe, output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
