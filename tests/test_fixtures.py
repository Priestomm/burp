"""The four reference captions, through extraction and structuring, with a fake model.

The fake answers are what a faithful model returns for each caption; the tests check what
the pipeline guarantees around it (source chosen, rules enforced). Whether the real model
answers like this is checked by the opt-in live tests in test_structure_live.py.
"""

from pathlib import Path

from burp.ingest import from_caption
from burp.models import Recipe
from burp.pipeline import import_post
from tests.test_structure import FakeClient, ingredient

CAPTIONS = Path(__file__).parent / "fixtures" / "captions"


def caption(name: str) -> str:
    return (CAPTIONS / f"{name}.txt").read_text()


def run(post, answer: Recipe, **kwargs):
    client = FakeClient(answer)
    return import_post(post, kwargs.pop("catalog"), client, "m", **kwargs), client


def test_complete_caption(catalog):
    answer = Recipe.model_validate(
        {
            "title": "Carbonara",
            "servings": 2,
            "time_minutes": 25,
            "ingredients": [
                ingredient("spaghetti", "200 g di spaghetti", 200, "g"),
                ingredient("guanciale", "100 g di guanciale", 100, "g"),
                ingredient("uovo", "3 tuorli + 1 uovo intero", 4),
                ingredient("Pecorino Romano", "50 g di pecorino romano grattugiato", 50, "g"),
                ingredient("pepe nero", "pepe nero macinato al momento", unit="q.b."),
            ],
            "steps": ["Rosola il guanciale.", "Sbatti uova e pecorino.", "Unisci la pasta."],
            "tags": {"cuisine": "italiana", "course": "primo", "diet": "neither"},
            "completeness": {"status": "complete", "missing": []},
        }
    )
    post = from_caption(caption("completa"), url="https://www.instagram.com/p/abc/?igsh=1")
    imported, client = run(post, answer, catalog=catalog)

    assert imported.content_source == "caption"
    assert "guanciale" in client.calls[0]["messages"][0]["content"]
    recipe = imported.recipe
    assert recipe.completeness.status == "complete"
    assert recipe.source_url == "https://www.instagram.com/p/abc/"
    assert "pecorino romano" in [i.canonical_name for i in recipe.ingredients]


def test_caption_with_missing_quantities_is_partial(catalog):
    answer = Recipe.model_validate(
        {
            "title": "Pasta zucchine e menta",
            "ingredients": [
                ingredient("pasta", "pasta corta (io ho usato le mezze maniche)"),
                ingredient("zucchina", "2 zucchine", 2),
                ingredient("menta", "menta fresca"),
                ingredient("pecorino", "pecorino grattugiato"),
                ingredient("olio d'oliva", "olio extravergine d'oliva"),
                ingredient("sale", "sale e pepe", unit="q.b."),
            ],
            "steps": ["Dora le zucchine.", "Cuoci la pasta e saltala.", "Aggiungi pecorino."],
            "tags": {"cuisine": "italiana", "course": "primo", "diet": "neither"},
            # A lazy model: it claims the recipe is complete.
            "completeness": {"status": "complete", "missing": []},
        }
    )
    imported, _ = run(from_caption(caption("quantita_mancanti")), answer, catalog=catalog)

    completeness = imported.recipe.completeness
    assert imported.content_source == "caption"
    assert completeness.status == "partial"
    assert completeness.missing == [
        "quantità di pasta",
        "quantità di menta",
        "quantità di pecorino romano",
        "quantità di olio d'oliva",
    ]
    # Quantities are never made up: what the caption does not say stays null.
    assert [i.quantity for i in imported.recipe.ingredients] == [None, 2, None, None, None, None]


def test_empty_caption_falls_back_to_the_transcript(catalog):
    class Transcriber:
        def transcribe(self, media_path):
            return (
                "Oggi facciamo la pasta e ceci. Ingredienti: 200 grammi di ceci, 80 g di pasta, "
                "uno spicchio d'aglio e rosmarino. Rosolate l'aglio nell'olio, aggiungete i ceci "
                "con il loro liquido, poi la pasta, e cuocete per dieci minuti mescolando spesso."
            )

    answer = Recipe.model_validate(
        {
            "title": "Pasta e ceci",
            "ingredients": [ingredient("ceci", "200 grammi di ceci", 200, "g")],
            "steps": ["Rosola l'aglio, aggiungi ceci e pasta."],
            "tags": {"diet": "vegan"},
            "completeness": {"status": "complete", "missing": []},
        }
    )
    post = from_caption(caption("vuota"))
    post.video_path = Path("reel.mp4")
    imported, client = run(post, answer, catalog=catalog, transcriber=Transcriber())

    assert imported.content_source == "transcript"
    assert imported.content_reason.startswith("caption: only")
    assert "200 grammi di ceci" in client.calls[0]["messages"][0]["content"]


def test_english_caption_is_saved_in_italian(catalog):
    answer = Recipe.model_validate(
        {
            "title": "Curry di ceci vegano",
            "servings": 4,
            "time_minutes": 30,
            "ingredients": [
                ingredient("olio di cocco", "2 tbsp coconut oil", 2, "cucchiaio"),
                ingredient("chickpeas", "2 cans (400 g each) chickpeas, drained", 800, "g"),
                ingredient("spinaci", "2 cups fresh spinach", 2, "tazza"),
                ingredient("sale", "salt to taste", unit="q.b."),
            ],
            "steps": ["Scalda l'olio e cuoci la cipolla per 5 minuti."],
            "tags": {"cuisine": "indiana", "course": "piatto unico", "diet": "vegan"},
            "completeness": {"status": "complete", "missing": []},
        }
    )
    imported, client = run(from_caption(caption("inglese")), answer, catalog=catalog)

    call = client.calls[0]
    assert "coconut milk" in call["messages"][0]["content"]  # the model sees the English text
    assert "Scrivi tutto in italiano" in call["system"][0]["text"]
    recipe = imported.recipe
    assert recipe.title == "Curry di ceci vegano"
    assert [i.canonical_name for i in recipe.ingredients][:2] == ["olio di cocco", "ceci"]
    assert recipe.ingredients[1].original_text.startswith("2 cans")  # kept verbatim
    assert recipe.completeness.status == "complete"
