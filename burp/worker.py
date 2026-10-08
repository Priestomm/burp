"""Background jobs: work that must not hold up an import, such as the dish photo.

The queue is a table in the library, so the bot, the CLI and the API can all add to it and
any process can run it: `burp worker`, or the thread the bot starts for itself.
"""

import contextlib
import logging
import threading
from pathlib import Path

from PIL import Image

from burp.library import Job, Library
from burp.photo import FramePicker, make_photo, stash_inputs, user_media
from burp.photocopy import DISH, photocopy

log = logging.getLogger(__name__)

PHOTO = "photo"
ZINE = "zine"  # prints for the Zine theme, after the photo


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


def run_once(library: Library, picker: FramePicker, media_dir: Path) -> bool:
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
            note = _run_zine(library, job.recipe_id, media_dir)
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


def _run_zine(library: Library, recipe_id: int, media_dir: Path) -> str:
    """Prints for the Zine theme, from the dish photo already chosen for Adesivi."""
    media = library.media(recipe_id)
    if media is None:
        return "nessuna foto del piatto da fotocopiare"
    with Image.open(media_dir / media.original) as original:
        sheet = landscape(original)
    printed = photocopy(sheet, width=900, exposure=DISH, seed=recipe_id)
    target = f"{recipe_id}/photocopy.png"
    printed.save(media_dir / target, optimize=True)
    library.set_zine_media(recipe_id, photocopy=target)
    return "fotocopia del piatto"


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
    open_library, picker: FramePicker, media_dir: Path, stop: threading.Event, idle: float = 2.0
) -> None:
    """Poll the queue until `stop` is set. `open_library` makes a connection for this thread."""
    with open_library() as library:
        while not stop.is_set():
            if not run_once(library, picker, media_dir):
                stop.wait(idle)


def start_in_background(open_library, picker: FramePicker, media_dir: Path) -> threading.Event:
    """Run the queue in a daemon thread; set the returned event to stop it."""
    stop = threading.Event()
    threading.Thread(
        target=run_forever,
        args=(open_library, picker, media_dir, stop),
        daemon=True,
        name="burp-worker",
    ).start()
    return stop
