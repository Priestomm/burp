"""Background jobs: work that must not hold up an import, such as the dish photo.

The queue is a table in the library, so the bot, the CLI and the API can all add to it and
any process can run it: `burp worker`, or the thread the bot starts for itself.
"""

import logging
import threading
from pathlib import Path

from burp.library import Library
from burp.photo import FramePicker, make_photo

log = logging.getLogger(__name__)

PHOTO = "photo"


def run_once(library: Library, picker: FramePicker, media_dir: Path) -> bool:
    """Run the oldest queued job. Returns False when there was nothing to do."""
    job = library.claim_job()
    if job is None:
        return False
    try:
        if job.kind != PHOTO:
            raise ValueError(f"unknown job kind {job.kind!r}")
        saved = library.get(job.recipe_id)
        if saved is None:
            raise ValueError(f"recipe #{job.recipe_id} is gone")
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
        library.finish_job(job.id, ok=True, note=outcome.note)
        log.info("job %d (%s #%d): %s", job.id, job.kind, job.recipe_id, outcome.note)
    except Exception as error:  # one bad job must not stop the queue
        log.exception("job %d failed", job.id)
        library.finish_job(job.id, ok=False, note=f"{type(error).__name__}: {error}")
    return True


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
