"""Pictures of the ingredients for the Zine theme: found, chosen, cut out, cached.

1. The fast model writes 1-2 English search queries for each ingredient (one call for the
   whole recipe) and says which ones are packaged products.
2. Candidates come from Open Food Facts (packaged products only) and from Pexels.
   Unsplash is not used: its API requires hotlinking its URLs, and we change the pictures.
3. The fast model picks the best of 3-5: one object, plain background, clear framing.
4. The picture is cut out with scissors and photocopied (cutout.py), and kept with its
   source, author, link and licence, which the page credits.

One picture per normalized ingredient name, reused by every recipe. With no good picture the
answer is cached too, and the page shows a paper slip with the name. Never generated images.
"""

import base64
import io
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import anthropic
import httpx
import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from burp.catalog import normalize_name
from burp.cutout import BackgroundRemover, make_cutout
from burp.photocopy import INGREDIENT, INK

log = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.5
MAX_CANDIDATES = 5
MIN_INK = 0.08  # a cut-out that is almost all blank paper lost its object
OFF_LICENSE = "CC BY-SA 3.0"
OFF_LICENSE_URL = "https://creativecommons.org/licenses/by-sa/3.0/"


@dataclass(frozen=True)
class Candidate:
    image_url: str  # a size good for cutting out
    thumb_url: str  # small, for the model to look at
    page_url: str  # where the picture lives, for the credit
    author: str
    author_url: str | None
    source: str  # "pexels" or "openfoodfacts"
    license: str


@dataclass(frozen=True)
class IngredientPicture:
    name: str  # normalized ingredient name, the cache key
    found: bool
    path: str | None = None  # relative to the media directory
    alt: str = ""
    source: str | None = None
    author: str | None = None
    author_url: str | None = None
    page_url: str | None = None
    license: str | None = None


class Source(Protocol):
    name: str

    def search(self, query: str, limit: int) -> list[Candidate]: ...


class PexelsSource:
    """Pexels API: free key, 200 requests an hour. Credit Pexels and the photographer."""

    name = "pexels"

    def __init__(self, api_key: str, client: httpx.Client) -> None:
        self.api_key = api_key
        self.client = client

    def search(self, query: str, limit: int) -> list[Candidate]:
        response = self.client.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": limit},
            headers={"Authorization": self.api_key},
        )
        response.raise_for_status()
        return [
            Candidate(
                image_url=photo["src"]["large"],
                thumb_url=photo["src"]["medium"],
                page_url=photo["url"],
                author=photo["photographer"],
                author_url=photo.get("photographer_url"),
                source=self.name,
                license="Pexels License",
            )
            for photo in response.json().get("photos", [])
        ]


class OpenFoodFactsSource:
    """Open Food Facts product photos: CC BY-SA 3.0, so our cut-outs are shared alike.
    Its search allows only a few requests a minute: they are spaced out."""

    name = "openfoodfacts"
    MIN_INTERVAL = 7.0  # seconds between searches

    def __init__(self, client: httpx.Client, sleep=time.sleep) -> None:
        self.client = client
        self.sleep = sleep
        self._last = 0.0

    def search(self, query: str, limit: int) -> list[Candidate]:
        wait = self._last + self.MIN_INTERVAL - time.monotonic()
        if wait > 0:
            self.sleep(wait)
        self._last = time.monotonic()
        response = self.client.get(
            "https://world.openfoodfacts.org/cgi/search.pl",
            params={
                "search_terms": query,
                "search_simple": 1,
                "json": 1,
                "page_size": limit,
                "fields": "product_name,brands,image_front_url,url",
            },
        )
        response.raise_for_status()
        return [
            Candidate(
                image_url=product["image_front_url"],
                thumb_url=product["image_front_url"],
                page_url=product["url"],
                author="Open Food Facts",
                author_url="https://openfoodfacts.org",
                source=self.name,
                license=OFF_LICENSE,
            )
            for product in response.json().get("products", [])
            if product.get("image_front_url") and product.get("url")
        ]


def http_client(contact: str | None) -> httpx.Client:
    """Open Food Facts asks apps to say who they are and how to reach them."""
    agent = f"burp/0.1 ({contact})" if contact else "burp/0.1"
    return httpx.Client(timeout=20, headers={"User-Agent": agent}, follow_redirects=True)


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Il nome dell'ingrediente, esattamente come ricevuto")
    queries: list[str] = Field(description="1-2 ricerche in inglese per una foto dell'ingrediente")
    packaged: bool = Field(description="true se di solito si compra confezionato con un marchio")
    product: str | None = Field(
        description="Se confezionato: il nome del prodotto da cercare in un catalogo di "
        "prodotti, semplice, es. 'gochujang', 'tahini'; altrimenti null"
    )


class Plans(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[Plan]


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    best: int = Field(description="Numero dell'immagine scelta (da 1), 0 se nessuna va bene")
    confidence: float = Field(ge=0, le=1)
    alt: str = Field(description="Cosa si vede, in italiano, una frase breve")


PLAN_PROMPT = """\
Per ogni ingrediente scrivi 1-2 ricerche in inglese per trovare una foto da banca immagini \
dell'ingrediente da solo, intero e riconoscibile, su sfondo semplice (es. "spring onion \
isolated", "silken tofu block"). packaged: true per prodotti di marca confezionati (salse, \
paste, condimenti in barattolo), false per ingredienti freschi o sfusi. product: per i \
confezionati, il nome semplice del prodotto come in un catalogo; altrimenti null."""

CHOICE_PROMPT = """\
Scegli la foto che mostra meglio l'ingrediente «{name}»: un solo oggetto, intero, nitido, su \
sfondo semplice, inquadrato bene, senza mani, persone o testo sopra. Deve essere una \
fotografia. Se nessuna va bene rispondi best = 0. alt: cosa si vede, in italiano."""


class Planner(Protocol):
    def plan(self, names: list[str]) -> dict[str, Plan]: ...


class Chooser(Protocol):
    def choose(self, name: str, thumbs: list[bytes]) -> Choice: ...


class ClaudePlanner:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self.client, self.model = client, model

    def plan(self, names: list[str]) -> dict[str, Plan]:
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=2000,
            system=PLAN_PROMPT,
            messages=[{"role": "user", "content": "\n".join(f"- {n}" for n in names)}],
            output_format=Plans,
        )
        plans = response.parsed_output.items if response.parsed_output else []
        return {plan.name: plan for plan in plans if plan.name in names}


class ClaudeChooser:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self.client, self.model = client, model

    def choose(self, name: str, thumbs: list[bytes]) -> Choice:
        content: list[dict] = []
        for number, data in enumerate(thumbs, start=1):
            content.append({"type": "text", "text": f"Immagine {number}:"})
            content.append(_jpeg_block(data))
        content.append({"type": "text", "text": CHOICE_PROMPT.format(name=name)})
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": content}],
            output_format=Choice,
        )
        if response.parsed_output is None:
            raise RuntimeError(f"no choice for {name!r} ({response.stop_reason})")
        return response.parsed_output


def _jpeg_block(data: bytes, longest: int = 512) -> dict:
    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGB")
        image.thumbnail((longest, longest))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=85)
    encoded = base64.standard_b64encode(buffer.getvalue()).decode()
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded},
    }


def ink_share(cut: Image.Image) -> float:
    """Share of the cut-out's paper covered by toner."""
    pixels = np.asarray(cut.convert("RGBA"))
    paper = pixels[..., 3] > 0
    if not paper.any():
        return 0.0
    ink = (pixels[..., :3] == INK).all(axis=-1) & paper
    return float(ink.sum() / paper.sum())


def slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "ingrediente"


class Finder:
    """Finds, cuts out and stores ingredient pictures; one network search per new name."""

    def __init__(
        self,
        planner: Planner,
        chooser: Chooser,
        sources: list[Source],
        remover: BackgroundRemover,
        download,  # url -> bytes
        media_dir: Path,
    ) -> None:
        self.planner, self.chooser, self.sources = planner, chooser, sources
        self.remover, self.download, self.media_dir = remover, download, media_dir

    def find(self, names: list[str]) -> list[IngredientPicture]:
        """For each of `names`: a picture, or a final "none" to cache. Names that could not
        be searched properly (an error, or no source for them yet) are left out, so they are
        tried again later, e.g. once a Pexels key is set."""
        plans = self.planner.plan(names) if names else {}
        results = (self._one(name, plans.get(name)) for name in names)
        return [picture for picture in results if picture is not None]

    def _one(self, name: str, plan: Plan | None) -> IngredientPicture | None:
        key = normalize_name(name)
        candidates: list[Candidate] = []
        searched = False
        for source, queries in self._searches(name, plan):
            for query in queries[:2]:
                if len(candidates) >= MAX_CANDIDATES:
                    break
                try:
                    candidates += source.search(query, MAX_CANDIDATES - len(candidates))
                    searched = True
                except httpx.HTTPError as error:
                    log.warning("ingredient %s: %s search failed: %s", name, source.name, error)
        candidates = candidates[:MAX_CANDIDATES]
        if not searched:
            return None  # nothing could be asked: try again another time
        if not candidates:
            return IngredientPicture(key, found=False)

        thumbs, usable = [], []
        for candidate in candidates:
            try:
                thumbs.append(self.download(candidate.thumb_url))
                usable.append(candidate)
            except httpx.HTTPError:
                continue
        if not usable:
            return IngredientPicture(key, found=False)
        choice = self.chooser.choose(name, thumbs)
        if not 1 <= choice.best <= len(usable) or choice.confidence < MIN_CONFIDENCE:
            return IngredientPicture(key, found=False)

        chosen = usable[choice.best - 1]
        with Image.open(io.BytesIO(self.download(chosen.image_url))) as picture:
            try:
                cut = make_cutout(
                    picture, self.remover, width=300, exposure=INGREDIENT, seed=len(key)
                )
            except ValueError:
                return IngredientPicture(key, found=False)
        if ink_share(cut) < MIN_INK:
            log.info("ingredient %s: cut-out almost blank, not used", name)
            return IngredientPicture(key, found=False)
        relative = f"ingredients/{slug(key)}.png"
        (self.media_dir / "ingredients").mkdir(parents=True, exist_ok=True)
        cut.save(self.media_dir / relative, optimize=True)
        return IngredientPicture(
            key,
            found=True,
            path=relative,
            alt=choice.alt,
            source=chosen.source,
            author=chosen.author,
            author_url=chosen.author_url,
            page_url=chosen.page_url,
            license=chosen.license,
        )

    def _searches(self, name: str, plan: Plan | None) -> list[tuple[Source, list[str]]]:
        """Packaged products: Open Food Facts first, by product name. Then the photo
        libraries, with the stock-photo queries. Fresh produce never from Open Food Facts."""
        queries = (plan.queries if plan else []) or [name]
        searches: list[tuple[Source, list[str]]] = []
        for source in self.sources:
            if source.name != "openfoodfacts":
                continue
            if plan and plan.packaged:
                searches.append((source, [plan.product or name]))
        searches += [(s, queries) for s in self.sources if s.name != "openfoodfacts"]
        return searches


def build_finder(settings, client: anthropic.Anthropic, remover: BackgroundRemover | None):
    """A Finder from the settings, or None when cut-outs are impossible (no rembg).
    Without a Pexels key only Open Food Facts is searched (packaged products)."""
    if remover is None:
        return None
    http = http_client(settings.contact_email)
    sources: list[Source] = [OpenFoodFactsSource(http)]
    if settings.pexels_api_key:
        sources.append(PexelsSource(settings.pexels_api_key, http))

    def download(url: str) -> bytes:
        response = http.get(url)
        response.raise_for_status()
        return response.content

    return Finder(
        ClaudePlanner(client, settings.fast_model),
        ClaudeChooser(client, settings.fast_model),
        sources,
        remover,
        download,
        settings.media_dir,
    )
