"""Background jobs: work that must not hold up an import, such as the dish photo.

The queue is a table in the library, so the bot, the CLI and the API can all add to it and
any process can run it: `burp worker`, or the thread the bot starts for itself.
"""

import contextlib
import importlib.util
import logging
import threading
from pathlib import Path

from PIL import Image

from burp.cutout import BackgroundRemover, RembgRemover, make_cutout
from burp.ingredient_images import Finder
from burp.library import Job, Library
from burp.photo import FramePicker, make_photo, stash_inputs, user_media
from burp.photocopy import colour_print

log = logging.getLogger(__name__)

PHOTO = "photo"
ZINE = "zine"  # prints for the Zine theme, after the photo
INGREDIENTS = "ingredients"  # Zine: pictures of the ingredients, cached by name


def queue_photo(
    library: Library,
    recipe_id: int,
    files: list[Path],
    media_dir: Path,
    reel: Path | None = None,
) -> int | None:
    """Queue the dish photo from what the user sent, plus the post's own video when the user
    opted in (`reel`). None when there is nothing usable."""
    usable = user_media(files)
    if not usable and reel is None:
        return None
    inputs = stash_inputs(recipe_id, usable, media_dir, reel=reel)
    return library.enqueue(PHOTO, recipe_id, inputs)


def default_remover() -> BackgroundRemover | None:
    """rembg if the optional `cutout` extra is installed; without it, no cut-outs."""
    return RembgRemover() if importlib.util.find_spec("rembg") else None


def run_once(
    library: Library,
    picker: FramePicker,
    media_dir: Path,
    remover: BackgroundRemover | None = None,
    finder: Finder | None = None,
) -> bool:
    """Run the oldest queued job. Returns False when there was nothing to do."""
    job = library.claim_job()
    if job is None:
        return False
    try:
        saved = library.get(job.recipe_id)
        if saved is None:
            raise ValueError(f"recipe #{job.recipe_id} is gone")
        if job.kind == PHOTO:
            note = _run_photo(library, job, saved, picker, media_dir)
        elif job.kind == ZINE:
            note = _run_zine(library, job.recipe_id, media_dir, remover)
        elif job.kind == INGREDIENTS:
            note = _run_ingredients(library, saved, finder)
        else:
            raise ValueError(f"unknown job kind {job.kind!r}")
        library.finish_job(job.id, ok=True, note=note)
        log.info("job %d (%s #%d): %s", job.id, job.kind, job.recipe_id, note)
    except Exception as error:  # one bad job must not stop the queue
        log.exception("job %d failed", job.id)
        library.finish_job(job.id, ok=False, note=f"{type(error).__name__}: {error}")
    finally:
        _discard_inputs(media_dir, job.inputs)
    return True


def _run_photo(library: Library, job: Job, saved, picker: FramePicker, media_dir: Path) -> str:
    outcome = make_photo(
        job.recipe_id,
        [media_dir / path for path in job.inputs],
        picker,
        media_dir,
        creator=saved.recipe.author_handle,
        source_url=saved.recipe.source_url,
    )
    if outcome.media is not None:
        library.set_media(job.recipe_id, outcome.media)
        library.enqueue(ZINE, job.recipe_id, [])  # the Zine prints come from the same photo
    return outcome.note


SHEET_RATIO = 1000 / 620  # the photocopy on the Zine page, as in the mockup


def landscape(image: Image.Image, ratio: float = SHEET_RATIO) -> Image.Image:
    """Centre crop to the sheet's proportions, so the page shows the whole print, torn edge
    included (reels are vertical; the dish is usually in the middle of the frame)."""
    width, height = image.size
    if width / height > ratio:
        new = round(height * ratio)
        left = (width - new) // 2
        return image.crop((left, 0, left + new, height))
    new = round(width / ratio)
    top = (height - new) // 2
    return image.crop((0, top, width, top + new))


def _run_ingredients(library: Library, saved, finder: Finder | None) -> str:
    """Pictures for the ingredients not seen before; the others come from the cache."""
    if finder is None:
        return "immagini degli ingredienti saltate: servono l'extra cutout e la chiave dell'AI"
    names = list(dict.fromkeys(i.canonical_name for i in saved.recipe.ingredients))
    new = [name for name in names if library.ingredient_picture(name) is None]
    for picture in finder.find(new):
        library.save_ingredient_picture(picture)
    found = sum(1 for name in names if (p := library.ingredient_picture(name)) and p.found)
    return f"{len(new)} cercati, {found} di {len(names)} con un'immagine"


def _run_zine(
    library: Library, recipe_id: int, media_dir: Path, remover: BackgroundRemover | None
) -> str:
    """The prints for the page (colour print and cut-out), from the dish photo already chosen."""
    media = library.media(recipe_id)
    if media is None:
        return "nessuna foto del piatto da fotocopiare"
    with Image.open(media_dir / media.original) as original:
        frame = original.convert("RGB")
    printed = colour_print(landscape(frame), width=900, seed=recipe_id)
    target = f"{recipe_id}/photocopy.png"
    printed.save(media_dir / target, optimize=True)
    notes = ["stampa del piatto"]

    if remover is None:
        notes.append("ritaglio saltato: installa l'extra cutout")
    else:
        try:
            cut = make_cutout(frame, remover, width=420, seed=recipe_id, colour=True)
        except ValueError as error:  # no clear object in the frame
            notes.append(f"nessun ritaglio ({error})")
        else:
            cutout = f"{recipe_id}/cutout.png"
            cut.save(media_dir / cutout, optimize=True)
            library.set_zine_media(recipe_id, cutout=cutout)
            notes.append("ritaglio del piatto")
    library.set_zine_media(recipe_id, photocopy=target)
    return ", ".join(notes)


def _discard_inputs(media_dir: Path, inputs: list[str]) -> None:
    """Only the chosen picture and its print are kept: no copies of videos or screenshots."""
    folders = set()
    for relative in inputs:
        path = media_dir / relative
        path.unlink(missing_ok=True)
        folders.add(path.parent)
    for folder in folders:
        with contextlib.suppress(OSError):  # not empty, or already gone
            folder.rmdir()


def run_forever(
    open_library,
    picker: FramePicker,
    media_dir: Path,
    stop: threading.Event,
    remover: BackgroundRemover | None = None,
    finder: Finder | None = None,
    idle: float = 2.0,
) -> None:
    """Poll the queue until `stop` is set. `open_library` makes a connection for this thread."""
    with open_library() as library:
        while not stop.is_set():
            if not run_once(library, picker, media_dir, remover, finder):
                stop.wait(idle)


def start_in_background(
    open_library,
    picker: FramePicker,
    media_dir: Path,
    remover: BackgroundRemover | None = None,
    finder: Finder | None = None,
) -> threading.Event:
    """Run the queue in a daemon thread; set the returned event to stop it."""
    stop = threading.Event()
    threading.Thread(
        target=run_forever,
        args=(open_library, picker, media_dir, stop, remover, finder),
        daemon=True,
        name="burp-worker",
    ).start()
    return stop
