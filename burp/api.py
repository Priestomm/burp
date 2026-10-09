"""HTTP API for the web app. Every response model is Pydantic, so the OpenAPI schema it
publishes is the single source of the TypeScript types in web/ (see `burp openapi`).

Local only for now: it binds to 127.0.0.1 and has no authentication.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import anthropic
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from burp.catalog import SynonymIndex, load_ingredients
from burp.config import Settings, anthropic_client
from burp.fill import ClaudeFiller, Filler
from burp.library import Cooked, Library, Media, SavedRecipe
from burp.models import Completeness, ContentSource, Course, Diet, Stroke, Tags
from burp.view import IngredientImage, IngredientView, ingredient_views, missing_names


class CookedOut(BaseModel):
    count: int
    last: str | None


class PhotoOut(BaseModel):
    src: str = Field(description="The halftone print, path under /api/media")
    original_src: str
    photocopy_src: str | None = Field(default=None, description="Zine: photocopied, torn edge")
    cutout_src: str | None = Field(default=None, description="Zine: the dish cut out")
    alt: str
    source: str = Field(description="frame (a video you sent), screenshot, or reel (the post's)")
    creator: str | None
    source_url: str | None


class NativeWord(BaseModel):
    lang: str = Field(description="BCP 47 language tag, e.g. ja")
    word: str
    meaning: str = Field(description="What it means, in Italian")


class Attribution(BaseModel):
    text: str
    url: str


class LibraryItem(BaseModel):
    id: int
    title: str
    nome_riga_1: str
    nome_riga_2: str | None
    diet: Diet
    course: Course | None
    cuisine: str | None
    to_clarify: int = Field(description="Quantities still unknown, plus 1 if there are no steps")
    cooked: CookedOut


class RecipeDetail(BaseModel):
    id: int
    created_at: str
    title: str
    nome_riga_1: str
    nome_riga_2: str | None
    descrittore: str | None
    source_url: str | None
    author_handle: str | None
    servings: int | None = Field(description="From the post, or the AI's estimate")
    servings_estimated: bool
    time_minutes: int | None
    time_estimated: bool
    tags: Tags
    ingredients: list[IngredientView]
    steps: list[str] = Field(description="Rewritten by the AI when filled, else as in the post")
    original_steps: list[str] = Field(description="As in the post")
    steps_rewritten: bool
    steps_note: str | None = Field(description="What the AI added to the steps")
    filled_by: str | None = Field(description="Model of 'Completa con l'AI', if shown")
    fill_saved: bool = Field(description="An AI completion is stored, shown or hidden")
    native_word: NativeWord | None = None
    attributions: list[Attribution] = Field(default_factory=list)
    still_missing: list[str] = Field(description="Ingredients whose quantity is still unknown")
    completeness: Completeness = Field(description="What the post did not say, as imported")
    content_source: ContentSource
    cooked: CookedOut
    photo: PhotoOut | None
    photo_pending: bool = Field(description="A dish photo is being made")
    drawing: list[Stroke] = Field(description="Marker strokes drawn on it, oldest first")


class DrawingIn(BaseModel):
    strokes: list[Stroke] = Field(max_length=500)


class DrawingOut(BaseModel):
    strokes: list[Stroke]


class QuantityIn(BaseModel):
    quantity: float = Field(gt=0)
    unit: str | None = None


class ByEyeIn(BaseModel):
    indices: list[int] = Field(min_length=1)


def to_clarify(saved: SavedRecipe) -> int:
    return len(missing_names(saved.imported)) + (0 if saved.recipe.steps else 1)


def _cooked(cooked: Cooked) -> CookedOut:
    return CookedOut(count=cooked.count, last=cooked.last)


def _photo(media: Media | None) -> PhotoOut | None:
    if media is None:
        return None
    return PhotoOut(
        src=f"/api/media/{media.halftone}",
        original_src=f"/api/media/{media.original}",
        alt=media.alt,
        source=media.source,
        creator=media.creator,
        source_url=media.source_url,
        photocopy_src=f"/api/media/{media.photocopy}" if media.photocopy else None,
        cutout_src=f"/api/media/{media.cutout}" if media.cutout else None,
    )


def _with_pictures(lib: Library, views: list[IngredientView]) -> tuple[list, list[Attribution]]:
    """Each ingredient with its cut-out, if there is one, and the credits they need."""
    credits: dict[str, Attribution] = {}
    out = []
    pexels = False
    for view in views:
        picture = lib.ingredient_picture(view.name)
        if picture is None or not picture.found:
            out.append(view)
            continue
        out.append(
            view.model_copy(
                update={"image": IngredientImage(src=f"/api/media/{picture.path}", alt=picture.alt)}
            )
        )
        if picture.source == "pexels":
            pexels = True
            text = f"{picture.author} su Pexels"
        else:
            text = f"{view.name}: Open Food Facts, {picture.license}"
        credits[picture.page_url] = Attribution(text=text, url=picture.page_url)
    if pexels:
        # Pexels asks for a visible link to Pexels besides the photographers' credits.
        credits["https://www.pexels.com"] = Attribution(
            text="Foto fornite da Pexels", url="https://www.pexels.com"
        )
    return out, list(credits.values())


def detail(lib: Library, saved: SavedRecipe) -> RecipeDetail:
    recipe = saved.recipe
    ingredients, attributions = _with_pictures(lib, ingredient_views(saved.imported))
    extra = saved.imported.shown_enrichment
    rewritten = bool(extra and extra.steps)
    return RecipeDetail(
        id=saved.id,
        created_at=saved.created_at,
        title=recipe.title,
        nome_riga_1=recipe.nome_riga_1,
        nome_riga_2=recipe.nome_riga_2,
        descrittore=recipe.descrittore,
        source_url=recipe.source_url,
        author_handle=recipe.author_handle,
        servings=recipe.servings or (extra.servings if extra else None),
        servings_estimated=recipe.servings is None and bool(extra and extra.servings),
        time_minutes=recipe.time_minutes or (extra.time_minutes if extra else None),
        time_estimated=recipe.time_minutes is None and bool(extra and extra.time_minutes),
        tags=recipe.tags,
        ingredients=ingredients,
        attributions=attributions,
        steps=extra.steps if rewritten else recipe.steps,
        original_steps=recipe.steps,
        steps_rewritten=rewritten,
        steps_note=extra.steps_note if extra else None,
        filled_by=extra.model if extra else None,
        native_word=(
            NativeWord(
                lang=recipe.parola_cucina.lingua,
                word=recipe.parola_cucina.parola,
                meaning=recipe.parola_cucina.traduzione,
            )
            if recipe.parola_cucina
            else None
        ),
        fill_saved=saved.imported.enrichment is not None,
        still_missing=missing_names(saved.imported),
        completeness=recipe.completeness,
        content_source=saved.imported.content_source,
        cooked=_cooked(lib.cooked(saved.id)),
        photo=_photo(lib.media(saved.id)),
        photo_pending=any(job.status in ("queued", "running") for job in lib.jobs(saved.id)),
        drawing=lib.drawing(saved.id),
    )


def create_app(
    db_path: Path | str | None = None,
    media_dir: Path | None = None,
    filler: Filler | None = None,
) -> FastAPI:
    settings = Settings.from_env()
    path = db_path or settings.db_path
    media_root = (media_dir or settings.media_dir).resolve()
    catalog = SynonymIndex(load_ingredients())
    app = FastAPI(
        title="burp!",
        version="0.1.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )

    # SQLite connections cannot cross threads, and FastAPI runs each request in a worker
    # thread: one short-lived connection per request.
    def library() -> Iterator[Library]:
        with Library(path, catalog) as lib:
            yield lib

    Lib = Annotated[Library, Depends(library)]

    def found(lib: Library, recipe_id: int) -> SavedRecipe:
        saved = lib.get(recipe_id)
        if saved is None:
            raise HTTPException(404, f"Non c'è nessuna ricetta #{recipe_id}.")
        return saved

    def changed(lib: Library, recipe_id: int, change) -> RecipeDetail:
        try:
            saved = change()
        except KeyError as error:
            raise HTTPException(404, f"Non c'è nessuna ricetta #{recipe_id}.") from error
        except IndexError as error:
            raise HTTPException(404, str(error)) from error
        return detail(lib, saved)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        """Opened in a browser by mistake: point to the dashboard."""
        return {
            "burp": "Questa è l'API di burp!. La dashboard è su http://localhost:3000 "
            "(cd web && pnpm dev).",
            "docs": "/api/docs",
        }

    @app.get("/api/media/{file_path:path}", operation_id="getMedia", include_in_schema=False)
    def media(file_path: str) -> FileResponse:
        target = (media_root / file_path).resolve()
        # Only the dish photos: nothing outside the media folder, not the stashed inputs.
        inside = target.is_relative_to(media_root) and "inputs" not in target.parts
        if not inside or not target.is_file():
            raise HTTPException(404, "Immagine non trovata.")
        return FileResponse(target, headers={"Cache-Control": "no-cache"})

    def get_filler() -> Filler:
        nonlocal filler
        if filler is None:
            if not settings.anthropic_api_key:
                raise HTTPException(503, "Manca ANTHROPIC_API_KEY: aggiungila a .env e riavvia.")
            client = anthropic_client(settings)
            filler = ClaudeFiller(client, settings.fast_model)
        return filler

    @app.post("/api/recipes/{recipe_id}/fill", operation_id="fillRecipe")
    def fill_recipe(lib: Lib, recipe_id: int, regenerate: bool = False) -> RecipeDetail:
        """Completa con l'AI: estimate what the post did not say and rewrite the steps.
        A stored completion is shown again for free; `regenerate` asks the model anew."""
        saved = found(lib, recipe_id)
        if saved.imported.enrichment is not None and not regenerate:
            return detail(lib, lib.show_enrichment(recipe_id, True))
        try:
            enrichment = get_filler().fill(saved.imported)
        except (anthropic.APIError, RuntimeError) as error:
            raise HTTPException(502, f"Il completamento non è riuscito: {error}") from error
        return detail(lib, lib.set_enrichment(recipe_id, enrichment))

    @app.delete("/api/recipes/{recipe_id}/fill", operation_id="clearFill")
    def clear_fill(lib: Lib, recipe_id: int) -> RecipeDetail:
        """Togli le stime: back to what the post says, plus the user's own edits. The
        completion stays stored, hidden, so showing it again needs no new call."""
        return changed(lib, recipe_id, lambda: lib.show_enrichment(recipe_id, False))

    @app.get("/api/recipes", operation_id="listRecipes")
    def list_recipes(lib: Lib, q: str | None = None) -> list[LibraryItem]:
        """The library, newest first; `q` keeps recipes where every word is in the title,
        the tags or the ingredients."""
        cooked = lib.cooked_all()
        return [
            LibraryItem(
                id=saved.id,
                title=saved.recipe.title,
                nome_riga_1=saved.recipe.nome_riga_1,
                nome_riga_2=saved.recipe.nome_riga_2,
                diet=saved.recipe.tags.diet,
                course=saved.recipe.tags.course,
                cuisine=saved.recipe.tags.cuisine,
                to_clarify=to_clarify(saved),
                cooked=_cooked(cooked.get(saved.id, Cooked(0, None))),
            )
            for saved in lib.search(text=q)
        ]

    @app.get("/api/recipes/{recipe_id}", operation_id="getRecipe")
    def get_recipe(lib: Lib, recipe_id: int) -> RecipeDetail:
        return detail(lib, found(lib, recipe_id))

    @app.put("/api/recipes/{recipe_id}/ingredients/{index}", operation_id="setQuantity")
    def set_quantity(lib: Lib, recipe_id: int, index: int, body: QuantityIn) -> RecipeDetail:
        """ "Li scrivo io": the user writes a quantity the post did not give."""
        return changed(
            lib, recipe_id, lambda: lib.set_quantity(recipe_id, index, body.quantity, body.unit)
        )

    @app.delete("/api/recipes/{recipe_id}/ingredients/{index}/edit", operation_id="clearEdit")
    def clear_edit(lib: Lib, recipe_id: int, index: int) -> RecipeDetail:
        return changed(lib, recipe_id, lambda: lib.clear_edit(recipe_id, index))

    @app.post("/api/recipes/{recipe_id}/by-eye", operation_id="markByEye")
    def mark_by_eye(lib: Lib, recipe_id: int, body: ByEyeIn) -> RecipeDetail:
        """ "Sì, a occhio": these quantities stay unknown, and that is fine."""
        return changed(lib, recipe_id, lambda: lib.mark_by_eye(recipe_id, body.indices))

    @app.put("/api/recipes/{recipe_id}/drawing", operation_id="setDrawing")
    def set_drawing(lib: Lib, recipe_id: int, body: DrawingIn) -> DrawingOut:
        """The marker: the whole drawing, sent again after every stroke or undo."""
        try:
            return DrawingOut(strokes=lib.set_drawing(recipe_id, body.strokes))
        except KeyError as error:
            raise HTTPException(404, f"Non c'è nessuna ricetta #{recipe_id}.") from error

    @app.delete("/api/recipes/{recipe_id}/drawing", operation_id="clearDrawing")
    def clear_drawing(lib: Lib, recipe_id: int) -> DrawingOut:
        try:
            return DrawingOut(strokes=lib.set_drawing(recipe_id, []))
        except KeyError as error:
            raise HTTPException(404, f"Non c'è nessuna ricetta #{recipe_id}.") from error

    @app.post("/api/recipes/{recipe_id}/cooked", operation_id="markCooked")
    def mark_cooked(lib: Lib, recipe_id: int) -> CookedOut:
        try:
            return _cooked(lib.cook(recipe_id))
        except KeyError as error:
            raise HTTPException(404, f"Non c'è nessuna ricetta #{recipe_id}.") from error

    return app
