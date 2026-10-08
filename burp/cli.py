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
import sys
import threading
from pathlib import Path

import anthropic

from burp.catalog import SynonymIndex, load_ingredients
from burp.config import Settings, load_env, setup_logging
from burp.frames import ClaudeFrameDescriber
from burp.ingest import SourcePost, fetch_instagram, from_caption, from_screenshots, from_video
from burp.library import Library
from burp.photo import ClaudeFramePicker
from burp.pipeline import import_post
from burp.render import full_text, one_line, summarize
from burp.structure import split_title
from burp.transcribe import FasterWhisperTranscriber
from burp.worker import queue_photo, run_forever, run_once


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="burp", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("import", help="import one recipe you share")
    add.add_argument("--url", help="Instagram post/reel link (also recorded as the source)")
    add.add_argument("--caption", help="caption text, pasted")
    add.add_argument("--caption-file", type=Path, help="file with the caption text")
    add.add_argument("--screenshot", nargs="+", type=Path, help="screenshot(s) of the recipe")
    add.add_argument("--video", type=Path, help="a video you have (screen recording, clip)")
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

    backfill = commands.add_parser(
        "backfill-titles", help="split the titles of recipes saved before the split existed"
    )
    backfill.add_argument("--dry-run", action="store_true", help="print, do not save")

    serve = commands.add_parser("serve", help="run the API for the web app (local only)")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true", help="restart on code changes")

    commands.add_parser("openapi", help="print the API schema (source of the web app types)")

    photo = commands.add_parser("photo", help="make the dish photo from your images or video")
    photo.add_argument("id", type=int)
    photo.add_argument("files", nargs="+", type=Path)

    reels = commands.add_parser(
        "photos-from-reels",
        help="dish photos from the reels of saved recipes (needs BURP_PHOTO_FROM_REEL=true)",
    )
    reels.add_argument("--dry-run", action="store_true", help="list them, download nothing")

    worker = commands.add_parser("worker", help="run background jobs (dish photos)")
    worker.add_argument("--once", action="store_true", help="empty the queue, then stop")

    commands.add_parser("bot", help="run the Telegram bot (it also runs the jobs)")

    args = parser.parse_args(argv)
    if args.command == "import" and not (
        args.url or args.caption or args.caption_file or args.screenshot or args.video
    ):
        add.error("give at least one of --url, --caption, --caption-file, --screenshot, --video")
    return args


def build_post(args: argparse.Namespace, settings: Settings) -> SourcePost:
    caption = args.caption or (args.caption_file.read_text() if args.caption_file else "")
    if args.video:
        post = from_video(args.video, url=args.url, caption=caption)
        post.screenshot_paths = list(args.screenshot or [])
        return post
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
    setup_logging()
    args = parse_args(argv)
    settings = Settings.from_env()
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "burp.api:create_app",
            factory=True,
            host="127.0.0.1",
            port=args.port,
            reload=args.reload,
        )
        return 0
    if args.command == "openapi":
        import json

        from burp.api import create_app

        print(json.dumps(create_app(":memory:").openapi(), indent=2, ensure_ascii=False))
        return 0
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
        case "backfill-titles":
            return backfill_titles(args, settings, library, client)
        case "photo":
            return attach_photo(args, settings, library)
        case "photos-from-reels":
            return photos_from_reels(args, settings, library)
        case "worker":
            return run_worker(args, settings, library, client)
        case "delete":
            if not library.delete(args.id):
                print(f"no recipe #{args.id}", file=sys.stderr)
                return 1
            print(f"deleted #{args.id}")
            return 0
    return 2


def backfill_titles(
    args: argparse.Namespace,
    settings: Settings,
    library: Library,
    client: anthropic.Anthropic | None,
) -> int:
    todo = [s for s in library.search() if needs_title_split(s.recipe)]
    if not todo:
        print("tutti i titoli sono già divisi")
        return 0
    if client is None:
        if not settings.anthropic_api_key:
            print("ANTHROPIC_API_KEY is not set (see .env.example)", file=sys.stderr)
            return 2
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    for saved in todo:
        split = split_title(saved.recipe.title, client, settings.fast_model)
        print(f"#{saved.id} {split.nome_riga_1} / {split.nome_riga_2 or '-'} · {split.descrittore}")
        if not args.dry_run:
            recipe = saved.recipe.model_copy(update=split.model_dump())
            library.replace(saved.id, saved.imported.model_copy(update={"recipe": recipe}))
    return 0


def needs_title_split(recipe) -> bool:
    """Upgraded recipes carry the whole title as the first line and nothing else."""
    return recipe.nome_riga_1 == recipe.title and not recipe.nome_riga_2 and not recipe.descrittore


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
        reel = post.downloaded_video if settings.photo_from_reel else None
        if created and queue_photo(
            library, saved.id, post.photo_inputs, settings.media_dir, reel=reel
        ):
            print("foto del piatto in coda: `burp worker` (o il bot) la prepara")
    return 0


def attach_photo(args: argparse.Namespace, settings: Settings, library: Library) -> int:
    if library.get(args.id) is None:
        print(f"no recipe #{args.id}", file=sys.stderr)
        return 1
    missing = [str(f) for f in args.files if not f.is_file()]
    if missing:
        print(f"file not found: {', '.join(missing)}", file=sys.stderr)
        return 1
    if queue_photo(library, args.id, args.files, settings.media_dir) is None:
        print("nessuna immagine o video tra i file (jpg, png, webp, mp4, mov)", file=sys.stderr)
        return 1
    print(f"foto del piatto in coda per #{args.id}")
    return 0


def photos_from_reels(args: argparse.Namespace, settings: Settings, library: Library) -> int:
    """Queue a photo from the reel of every saved recipe that has none (opt-in)."""
    if not settings.photo_from_reel:
        print(
            "Spento: per usare i video dei reel metti BURP_PHOTO_FROM_REEL=true in .env "
            "(solo per uso personale, vedi README).",
            file=sys.stderr,
        )
        return 2
    todo = [
        saved
        for saved in library.search()
        if saved.recipe.source_url
        and library.media(saved.id) is None
        and not any(job.status in ("queued", "running") for job in library.jobs(saved.id))
    ]
    if not todo:
        print("nessuna ricetta da reel senza foto")
        return 0
    for saved in todo:
        if args.dry_run:
            print(f"#{saved.id} {saved.recipe.title}")
            continue
        try:
            post = fetch_instagram(
                saved.recipe.source_url, cookies_file=settings.instagram_cookies_file
            )
        except RuntimeError as error:
            print(f"#{saved.id}: non scaricato ({error})", file=sys.stderr)
            continue
        if post.downloaded_video is None:
            print(f"#{saved.id}: nessun video nel post", file=sys.stderr)
            continue
        queue_photo(library, saved.id, [], settings.media_dir, reel=post.downloaded_video)
        print(f"#{saved.id}: foto in coda")
    return 0


def run_worker(
    args: argparse.Namespace,
    settings: Settings,
    library: Library,
    client: anthropic.Anthropic | None,
) -> int:
    if client is None:
        if not settings.anthropic_api_key:
            print("ANTHROPIC_API_KEY is not set (see .env.example)", file=sys.stderr)
            return 2
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    picker = ClaudeFramePicker(client, settings.fast_model)
    if args.once:
        while run_once(library, picker, settings.media_dir):
            pass
        return 0
    print("worker avviato: Ctrl+C per fermarlo")
    stop = threading.Event()
    try:
        run_forever(lambda: library, picker, settings.media_dir, stop)
    except KeyboardInterrupt:
        stop.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
