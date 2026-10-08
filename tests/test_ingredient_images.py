import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image, ImageDraw

from burp.ingredient_images import (
    Candidate,
    Choice,
    Finder,
    OpenFoodFactsSource,
    PexelsSource,
    Plan,
    http_client,
    slug,
)
from tests.test_scissors import ColourRemover


def object_png() -> bytes:
    """A dark round thing on a pale background, like a stock photo of an onion."""
    image = Image.new("RGB", (240, 200), (240, 236, 230))
    ImageDraw.Draw(image).ellipse((60, 40, 180, 160), fill=(70, 90, 40))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class FakeSource:
    def __init__(self, name):
        self.name, self.queries = name, []

    def search(self, query, limit):
        self.queries.append(query)
        return [
            Candidate(
                image_url=f"https://{self.name}/{query}/{i}.jpg",
                thumb_url=f"https://{self.name}/t{i}.jpg",
                page_url=f"https://{self.name}/page/{i}",
                author=f"Autore {i}",
                author_url=None,
                source=self.name,
                license="licenza",
            )
            for i in range(min(limit, 3))
        ]


class FakePlanner:
    def __init__(self, packaged=()):
        self.packaged, self.calls = set(packaged), []

    def plan(self, names):
        self.calls.append(list(names))
        return {
            n: Plan(
                name=n,
                queries=[f"{n} isolated"],
                packaged=n in self.packaged,
                product=n if n in self.packaged else None,
            )
            for n in names
        }


class FakeChooser:
    def __init__(self, best=2, confidence=0.9):
        self.best, self.confidence, self.calls = best, confidence, []

    def choose(self, name, thumbs):
        self.calls.append((name, len(thumbs)))
        return Choice(best=self.best, confidence=self.confidence, alt=f"Un {name} su fondo chiaro")


@pytest.fixture
def parts(tmp_path):
    off, pexels = FakeSource("openfoodfacts"), FakeSource("pexels")
    downloaded = []

    def download(url):
        downloaded.append(url)
        return object_png()

    def make(planner=None, chooser=None):
        return Finder(
            planner or FakePlanner(),
            chooser or FakeChooser(),
            [off, pexels],
            ColourRemover(),
            download,
            tmp_path,
        )

    return make, off, pexels, downloaded, tmp_path


def test_a_fresh_ingredient_is_searched_chosen_cut_out_and_credited(parts):
    make, off, pexels, downloaded, media = parts
    chooser = FakeChooser(best=2)
    [picture] = make(chooser=chooser).find(["cipollotto"])
    assert picture.found and picture.path == "ingredients/cipollotto.png"
    assert (media / picture.path).exists()
    assert (picture.source, picture.author, picture.page_url) == (
        "pexels",
        "Autore 1",
        "https://pexels/page/1",
    )
    assert picture.alt == "Un cipollotto su fondo chiaro"
    assert off.queries == []  # fresh produce: not from Open Food Facts
    assert pexels.queries == ["cipollotto isolated"]
    assert chooser.calls == [("cipollotto", 3)]
    assert downloaded[-1] == "https://pexels/cipollotto isolated/1.jpg"  # the full-size one


def test_packaged_products_look_at_open_food_facts_first(parts):
    make, off, pexels, _, _ = parts
    [picture] = make(planner=FakePlanner(packaged={"gochujang"})).find(["gochujang"])
    assert off.queries == ["gochujang"]  # by product name, not the stock-photo query
    assert picture.source == "openfoodfacts"


def test_no_good_picture_is_an_answer_too(parts):
    make, *_ = parts
    [unsure] = make(chooser=FakeChooser(confidence=0.3)).find(["latte"])
    [nothing] = make(chooser=FakeChooser(best=0)).find(["acqua"])
    assert not unsure.found and not nothing.found and unsure.path is None


def test_one_planning_call_for_all_the_ingredients(parts):
    make, *_ = parts
    planner = FakePlanner()
    make(planner=planner).find(["tofu", "cipollotto", "sale"])
    assert planner.calls == [["tofu", "cipollotto", "sale"]]


def test_slug():
    assert slug("semi di sesamo") == "semi-di-sesamo"
    assert slug("Crème fraîche") == "creme-fraiche"


def test_pexels_source_reads_the_api():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("Authorization")
        seen["query"] = request.url.params["query"]
        photo = {
            "url": "https://www.pexels.com/photo/onion-1/",
            "photographer": "Ada Rossi",
            "photographer_url": "https://www.pexels.com/@ada",
            "src": {
                "large": "https://images.pexels.com/1-large.jpg",
                "medium": "https://images.pexels.com/1-m.jpg",
            },
        }
        return httpx.Response(200, json={"photos": [photo]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    [candidate] = PexelsSource("KEY", client).search("spring onion", 5)
    assert seen == {"auth": "KEY", "query": "spring onion"}
    assert (candidate.author, candidate.source) == ("Ada Rossi", "pexels")
    assert candidate.image_url.endswith("large.jpg") and candidate.thumb_url.endswith("m.jpg")


def test_open_food_facts_source_skips_products_without_a_picture():
    def handler(request):
        products = [
            {
                "product_name": "Gochujang",
                "image_front_url": "https://images.openfoodfacts.org/1.jpg",
                "url": "https://world.openfoodfacts.org/product/1",
            },
            {"product_name": "Senza foto", "url": "https://world.openfoodfacts.org/product/2"},
        ]
        return httpx.Response(200, json={"products": products})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    [candidate] = OpenFoodFactsSource(client).search("gochujang", 5)
    assert candidate.license == "CC BY-SA 3.0" and candidate.source == "openfoodfacts"


def test_user_agent_says_who_we_are():
    assert http_client("tomm@example.com").headers["User-Agent"] == "burp/0.1 (tomm@example.com)"
    assert http_client(None).headers["User-Agent"] == "burp/0.1"


def test_worker_searches_each_name_once_across_recipes(library, tmp_path):
    from burp.models import ImportedRecipe
    from burp.worker import INGREDIENTS, run_once
    from tests.test_structure import ingredient, valid_recipe

    planner = FakePlanner()
    finder = Finder(
        planner,
        FakeChooser(),
        [FakeSource("pexels")],
        ColourRemover(),
        lambda _: object_png(),
        tmp_path,
    )
    for title in ("Gnocchi", "Zuppa"):
        recipe = valid_recipe(title=title, ingredients=[ingredient("cipollotto", "cipollotto")])
        saved, _ = library.add(ImportedRecipe(recipe=recipe, content_source="caption"))
        library.enqueue(INGREDIENTS, saved.id, [])
    run_once(library, None, tmp_path, None, finder)
    run_once(library, None, tmp_path, None, finder)
    assert planner.calls == [["cipollotto"]]  # the second recipe used the cache
    assert library.ingredient_picture("Cipollotto").found
    assert "0 cercati, 1 di 1" in library.jobs(2)[0].note


def test_api_shows_pictures_and_credits(tmp_path):
    from fastapi.testclient import TestClient

    from burp.api import create_app
    from burp.ingredient_images import IngredientPicture
    from burp.library import Library
    from burp.models import ImportedRecipe
    from tests.test_structure import ingredient, valid_recipe

    db = tmp_path / "burp.db"
    names = [ingredient("cipollotto", "x"), ingredient("gochujang", "y")]
    with Library(db) as lib:
        lib.add(ImportedRecipe(recipe=valid_recipe(ingredients=names), content_source="caption"))
        lib.save_ingredient_picture(
            IngredientPicture(
                name="cipollotto",
                found=True,
                path="ingredients/cipollotto.png",
                alt="Un cipollotto",
                source="pexels",
                author="Ada Rossi",
                page_url="https://www.pexels.com/photo/1/",
                license="Pexels License",
            )
        )
        lib.save_ingredient_picture(
            IngredientPicture(
                name="gochujang",
                found=True,
                path="ingredients/gochujang.png",
                alt="Barattolo",
                source="openfoodfacts",
                author="Open Food Facts",
                page_url="https://world.openfoodfacts.org/product/1",
                license="CC BY-SA 3.0",
            )
        )
    data = TestClient(create_app(db, tmp_path / "media")).get("/api/recipes/1").json()
    assert data["ingredients"][0]["image"] == {
        "src": "/api/media/ingredients/cipollotto.png",
        "alt": "Un cipollotto",
        "clip": "none",
    }
    credits = {a["text"]: a["url"] for a in data["attributions"]}
    assert credits["Ada Rossi su Pexels"] == "https://www.pexels.com/photo/1/"
    assert credits["Foto fornite da Pexels"] == "https://www.pexels.com"
    assert credits["gochujang: Open Food Facts, CC BY-SA 3.0"].endswith("/product/1")
    assert json.dumps(data)  # serializable


def test_finder_needs_a_remover():
    from types import SimpleNamespace

    from burp.ingredient_images import build_finder

    assert build_finder(SimpleNamespace(), client=None, remover=None) is None


def test_media_dir_is_used(parts):
    make, *_rest, media = parts
    make().find(["tofu"])
    assert (Path(media) / "ingredients" / "tofu.png").exists()


def test_failed_searches_are_not_cached_as_no_picture(tmp_path):
    class Down:
        name = "pexels"

        def search(self, query, limit):
            raise httpx.ConnectError("offline")

    finder = Finder(
        FakePlanner(), FakeChooser(), [Down()], ColourRemover(), lambda _: b"", tmp_path
    )
    assert finder.find(["cipollotto"]) == []  # nothing to cache: try again later


def test_fresh_produce_without_a_photo_library_is_not_cached(tmp_path):
    off = FakeSource("openfoodfacts")
    finder = Finder(FakePlanner(), FakeChooser(), [off], ColourRemover(), lambda _: b"", tmp_path)
    assert finder.find(["cipollotto"]) == []  # once a Pexels key is set, it will be searched
    assert off.queries == []


def test_open_food_facts_searches_are_spaced_out():
    slept = []
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    source = OpenFoodFactsSource(client, sleep=slept.append)
    source.search("a", 5)
    source.search("b", 5)
    assert len(slept) == 1 and 6 < slept[0] <= OpenFoodFactsSource.MIN_INTERVAL


def test_an_almost_blank_cut_out_is_not_used(tmp_path):
    from burp.ingredient_images import ink_share

    blank = Image.new("RGB", (240, 200), (240, 236, 230))
    ImageDraw.Draw(blank).rectangle((60, 40, 180, 160), fill=(225, 222, 216))  # a white box
    buffer = io.BytesIO()
    blank.save(buffer, "PNG")

    class KeepAll:
        def remove(self, image):
            rgba = image.convert("RGBA")
            return rgba

    finder = Finder(FakePlanner(), FakeChooser(), [FakeSource("pexels")], KeepAll(),
                    lambda _: buffer.getvalue(), tmp_path)  # fmt: skip
    [picture] = finder.find(["fecola di patate"])
    assert not picture.found
    assert ink_share(Image.new("RGBA", (4, 4), (0, 0, 0, 0))) == 0.0
