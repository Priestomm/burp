"""Content extraction with increasing cost: caption, then audio transcript, then video frames.

Each step runs only if the previous one was not enough. The source finally used, and why the
cheaper ones were rejected, is logged and returned so it can be stored with the recipe.
"""

import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from burp.frames import FrameDescriber, extract_frames
from burp.ingest import SourcePost
from burp.transcribe import Transcriber

log = logging.getLogger(__name__)

Source = Literal["caption", "transcript", "frames"]

MIN_WORDS = 25
QUANTITY = re.compile(
    r"\d+\s*(?:g|gr|kg|ml|l|cl|dl|oz|lb|cups?|tbsp|tsp|cucchiai\w*|cucchiaini?|spicchi\w*|"
    r"tazz\w*|bicchier\w*|pizzic\w*)\b|\bq\.?\s?b\.?\b|\bingredient\w*",
    re.IGNORECASE,
)
NOISE = re.compile(r"#\w+|@\w+|https?://\S+")
# A procedure: a heading, or at least MIN_STEP_VERBS different cooking verbs. Italian verbs are
# matched as stem + ending (cuoci, cuocete, cuocere, cuociamo...) so that nouns such as
# "impasto" or "tagliatelle" do not count.
STEPS_HEADING = re.compile(
    r"\b(?:procedimento|preparazione|come si fa|istruzioni|method|steps|directions|"
    r"instructions)\b",
    re.IGNORECASE,
)
STEP_VERB = re.compile(
    r"\b(?:(?P<it>cuoc|aggiung|mescol|vers|tagli|rosol|inforn|scol|frull|impast|incorpor|"
    r"sbatt|soffrigg|frigg|lasci|scald|sciogl|trit|condisc|stend|copr|mett|unisc|spegn|"
    r"sfum|lav|sbucci|grattugi|amalgam|riduc|pel)"
    r"(?:a|e|i|ate|ete|ite|are|ere|ire|iamo|ando|endo)(?:l[aeio]|ne)?"
    r"|(?P<en>cook|add|mix|stir|bake|heat|pour|chop|boil|fry|whisk|simmer|combine|blend|"
    r"preheat|drain|slice|knead|roast|saut[eé])(?:s|ed|ing)?)\b",
    re.IGNORECASE,
)
MIN_STEP_VERBS = 2


class InsufficientContentError(RuntimeError):
    """No source produced enough text to build a recipe from."""


@dataclass
class ExtractedContent:
    text: str
    source: Source
    reason: str  # why the cheaper sources were not enough ("" if the caption was fine)


def is_sufficient(text: str) -> tuple[bool, str]:
    """Deterministic check that a text looks like a recipe. Returns (ok, reason if not)."""
    words = re.findall(r"[^\W\d_]{2,}", NOISE.sub(" ", text))
    if len(words) < MIN_WORDS:
        return False, f"only {len(words)} words of text (need {MIN_WORDS})"
    if not QUANTITY.search(text):
        return False, "no quantities or ingredient list found"
    if not has_steps(text):
        return False, "no steps found (only ingredients)"
    return True, ""


def has_steps(text: str) -> bool:
    if STEPS_HEADING.search(text):
        return True
    verbs = {(m["it"] or m["en"]).lower() for m in STEP_VERB.finditer(text)}
    return len(verbs) >= MIN_STEP_VERBS


def extract_content(
    post: SourcePost,
    transcriber: Transcriber | None = None,
    describer: FrameDescriber | None = None,
    frame_count: int = 6,
) -> ExtractedContent:
    ok, reason = is_sufficient(post.caption)
    if ok:
        return _chosen(ExtractedContent(post.caption, "caption", ""))
    reasons = [f"caption: {reason}"]

    if post.video_path and transcriber:
        try:
            transcript = transcriber.transcribe(post.video_path)
        except RuntimeError as error:  # e.g. faster-whisper not installed
            reasons.append(f"transcript: failed ({error})")
        else:
            text = f"{post.caption}\n\n{transcript}".strip()
            ok, reason = is_sufficient(text)
            if ok:
                return _chosen(ExtractedContent(text, "transcript", "; ".join(reasons)))
            reasons.append(f"transcript: {reason}")
    elif post.video_path:
        reasons.append("transcript: skipped, no transcriber available")
    else:
        reasons.append("transcript: skipped, no video")

    if describer:
        images = _collect_images(post, frame_count, reasons)
        if images:
            description = describer.describe(images)
            text = f"{post.caption}\n\n{description}".strip()
            reasons.append(f"frames: {len(images)} images analysed")
            return _chosen(ExtractedContent(text, "frames", "; ".join(reasons)))
        reasons.append("frames: no video or screenshots to analyse")

    raise InsufficientContentError(
        "not enough content to build a recipe (" + "; ".join(reasons) + "). "
        "Paste the full caption or send a screenshot of the recipe."
    )


def _chosen(content: ExtractedContent) -> ExtractedContent:
    log.info("content source: %s (%s)", content.source, content.reason or "caption sufficient")
    return content


def _collect_images(post: SourcePost, frame_count: int, reasons: list[str]) -> list[Path]:
    images = list(post.screenshot_paths)
    if post.video_path:
        out_dir = Path(tempfile.mkdtemp(prefix="burp-frames-"))
        try:
            images += extract_frames(post.video_path, out_dir, frame_count)
        except RuntimeError as error:  # e.g. PyAV not installed
            reasons.append(f"frames: could not extract video frames ({error})")
    return images
