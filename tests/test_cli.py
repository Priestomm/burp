from pathlib import Path

import pytest

from burp.cli import main
from tests.test_structure import FakeClient, ingredient, valid_recipe

CAPTIONS = Path(__file__).parent / "fixtures" / "captions"
URL = "https://www.instagram.com/p/abc/"


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch, tmp_path):
    monkeypatch.setattr("burp.cli.load_env", lambda: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("BURP_MEDIA_DIR", str(tmp_path / "media"))


def test_caption_file_is_imported_and_saved(library, capsys):
    client = FakeClient(valid_recipe())
    args = ["import", "--caption-file", str(CAPTIONS / "completa.txt"), "--url", URL + "?igsh=1"]
    assert main(args, client=client, library=library) == 0

    [saved] = library.search()
    assert saved.recipe.source_url == URL
    assert saved.imported.content_source == "caption"
    out = capsys.readouterr().out
    assert "completa" in out and f"salvata come #{saved.id}" in out
    assert "guanciale" in client.calls[0]["messages"][0]["content"]  # the caption reached it


def test_a_link_already_in_the_library_costs_nothing(library, capsys, monkeypatch):
    first = FakeClient(valid_recipe())
    caption = (CAPTIONS / "completa.txt").read_text()
    main(["import", "--caption", caption, "--url", URL], client=first, library=library)

    def no_fetch(*args, **kwargs):
        raise AssertionError("must not download")

    monkeypatch.setattr("burp.cli.fetch_instagram", no_fetch)
    capsys.readouterr()
    client = FakeClient()  # any call to the model would fail: nothing is queued
    args = ["import", "--url", "https://instagram.com/reel/abc"]
    assert main(args, client=client, library=library) == 0
    assert "già in libreria (#1): Dal tadka" in capsys.readouterr().out
    assert client.calls == []
    assert len(library.search()) == 1


def test_dry_run_saves_nothing(library, capsys):
    args = ["import", "--caption", (CAPTIONS / "completa.txt").read_text(), "--dry-run"]
    assert main(args, client=FakeClient(valid_recipe()), library=library) == 0
    assert library.search() == []
    assert "dry run" in capsys.readouterr().out


def test_partial_recipe_is_saved_and_reported(library, capsys):
    partial = valid_recipe(
        title="Pasta zucchine e menta",
        ingredients=[ingredient("pasta", "pasta corta")],
    )
    args = ["import", "--caption-file", str(CAPTIONS / "quantita_mancanti.txt")]
    assert main(args, client=FakeClient(partial), library=library) == 0
    assert library.search()[0].recipe.completeness.status == "partial"
    assert "parziale, manca: quantità di pasta" in capsys.readouterr().out


def test_empty_caption_without_fallback_asks_for_manual_input(library, capsys):
    args = ["import", "--caption-file", str(CAPTIONS / "vuota.txt")]
    assert main(args, client=FakeClient(), library=library) == 1
    assert "Paste the full caption" in capsys.readouterr().err
    assert library.search() == []


def test_missing_api_key_is_reported(library, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert main(["import", "--caption", "x"], library=library) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_import_needs_some_input(library):
    with pytest.raises(SystemExit):
        main(["import"], library=library)


def fill(library):
    from burp.models import ImportedRecipe

    for recipe in (
        valid_recipe(title="Pasta e ceci", tags={"course": "primo", "diet": "vegan"}),
        valid_recipe(
            title="Carbonara",
            ingredients=[ingredient("guanciale", "100 g di guanciale", 100, "g")],
            tags={"cuisine": "italiana", "course": "primo", "diet": "neither"},
        ),
    ):
        library.add(ImportedRecipe(recipe=recipe, content_source="caption"))


def test_search_prints_one_line_per_recipe(library, capsys):
    fill(library)
    assert main(["search", "--tag", "primo", "--ingredient", "guanciale"], library=library) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out == ["#2    Carbonara  (italiana, primo, né vegana né vegetariana)"]


def test_search_by_title_and_no_results(library, capsys):
    fill(library)
    main(["search", "pasta"], library=library)
    assert "Pasta e ceci" in capsys.readouterr().out
    main(["search", "risotto"], library=library)
    assert "nessuna ricetta trovata" in capsys.readouterr().out


def test_show_prints_the_whole_recipe(library, capsys):
    fill(library)
    assert main(["show", "2"], library=library) == 0
    out = capsys.readouterr().out
    assert "#2 Carbonara" in out
    assert "- guanciale: 100 g  [100 g di guanciale]" in out
    assert "1. Cuoci le lenticchie." in out


def test_show_and_delete_unknown_ids_fail(library, capsys):
    assert main(["show", "9"], library=library) == 1
    assert main(["delete", "9"], library=library) == 1


def test_delete(library, capsys):
    fill(library)
    assert main(["delete", "1"], library=library) == 0
    assert [s.recipe.title for s in library.search()] == ["Carbonara"]


def test_backfill_splits_only_titles_that_were_never_split(library, capsys):
    from burp.models import ImportedRecipe
    from burp.structure import TitleSplit

    title = "Gnocchi di tofu gommosi glassati"
    old = valid_recipe(title=title, nome_riga_1=title, nome_riga_2=None)
    new = valid_recipe(title="Carbonara", nome_riga_1="Carbonara", descrittore="vera")
    library.add(ImportedRecipe(recipe=old, content_source="caption"))
    library.add(ImportedRecipe(recipe=new, content_source="caption"))
    split = TitleSplit(
        nome_riga_1="Gnocchi", nome_riga_2="di tofu", descrittore="gommosi e glassati"
    )
    client = FakeClient(split)

    assert main(["backfill-titles"], client=client, library=library) == 0
    assert len(client.calls) == 1 and "Gnocchi di tofu" in client.calls[0]["messages"][0]["content"]
    recipe = library.get(1).recipe
    assert (recipe.nome_riga_1, recipe.nome_riga_2, recipe.descrittore) == (
        "Gnocchi",
        "di tofu",
        "gommosi e glassati",
    )
    assert library.get(2).recipe.descrittore == "vera"
    capsys.readouterr()
    assert main(["backfill-titles"], client=FakeClient(), library=library) == 0
    assert "già divisi" in capsys.readouterr().out


DISH = Path(__file__).parent / "fixtures" / "images" / "piatto.jpg"


def test_screenshots_from_an_import_queue_the_dish_photo(library, capsys, tmp_path):
    args = ["import", "--caption-file", str(CAPTIONS / "completa.txt"), "--screenshot", str(DISH)]
    assert main(args, client=FakeClient(valid_recipe()), library=library) == 0
    assert "foto del piatto in coda" in capsys.readouterr().out
    assert [j.kind for j in library.jobs(1)] == ["ingredients", "photo"]
    job = library.jobs(1)[1]
    assert job.status == "queued"
    assert (tmp_path / "media" / job.inputs[0]).exists()


def test_photo_then_worker_once(library, capsys, tmp_path):
    from burp.models import ImportedRecipe
    from burp.photo import Pick

    library.add(ImportedRecipe(recipe=valid_recipe(), content_source="caption"))
    assert main(["photo", "1", str(DISH)], library=library) == 0
    pick = Pick(best=1, confidence=0.8, alt="Un piatto di gnocchi", reason="nitida")
    assert main(["worker", "--once"], client=FakeClient(pick), library=library) == 0
    media = library.media(1)
    assert media.alt == "Un piatto di gnocchi"
    assert (tmp_path / "media" / media.halftone).exists()


def test_photo_rejects_unknown_recipes_and_files(library, capsys, tmp_path):
    assert main(["photo", "9", str(DISH)], library=library) == 1
    from burp.models import ImportedRecipe

    library.add(ImportedRecipe(recipe=valid_recipe(), content_source="caption"))
    notes = tmp_path / "notes.txt"
    notes.write_text("x")
    assert main(["photo", "1", str(notes)], library=library) == 1
    assert main(["photo", "1", str(tmp_path / "nope.jpg")], library=library) == 1


def test_photos_from_reels_is_off_by_default(library, capsys, monkeypatch):
    monkeypatch.delenv("BURP_PHOTO_FROM_REEL", raising=False)
    assert main(["photos-from-reels"], library=library) == 2
    assert "BURP_PHOTO_FROM_REEL" in capsys.readouterr().err


def test_photos_from_reels_queues_the_recipes_without_a_photo(
    library, capsys, monkeypatch, tmp_path
):
    from burp.ingest import SourcePost
    from burp.models import ImportedRecipe

    monkeypatch.setenv("BURP_PHOTO_FROM_REEL", "true")
    reel = tmp_path / "post.mp4"
    reel.write_bytes(b"video")
    fetched = []

    def fetch(url, cookies_file=None):
        fetched.append(url)
        return SourcePost(url=url, video_path=reel)

    monkeypatch.setattr("burp.cli.fetch_instagram", fetch)
    url = "https://www.instagram.com/reel/abc/"
    library.add(ImportedRecipe(recipe=valid_recipe(source_url=url), content_source="caption"))
    library.add(ImportedRecipe(recipe=valid_recipe(), content_source="caption"))  # no link

    assert main(["photos-from-reels", "--dry-run"], library=library) == 0
    assert fetched == [] and "#1" in capsys.readouterr().out
    assert main(["photos-from-reels"], library=library) == 0
    assert fetched == [url]
    assert [Path(p).name for p in library.jobs(1)[0].inputs] == ["reel.mp4"]
    assert library.jobs(2) == []
    # Queued already: a second run does not download it again.
    main(["photos-from-reels"], library=library)
    assert fetched == [url]


def test_zine_images_queues_prints_and_ingredient_pictures(library, capsys):
    from burp.library import Media
    from burp.models import ImportedRecipe

    for _ in range(3):
        library.add(ImportedRecipe(recipe=valid_recipe(), content_source="caption"))
    library.set_media(1, Media("1/original.jpg", "1/halftone.png", "reel", 0.9, "x", None, None))
    library.set_media(2, Media("2/original.jpg", "2/halftone.png", "reel", 0.9, "x", None, None))
    library.set_zine_media(2, photocopy="2/photocopy.png")
    assert main(["zine-images"], library=library) == 0
    assert [j.kind for j in library.jobs(1)] == ["zine", "ingredients"]
    assert [j.kind for j in library.jobs(2)] == ["ingredients"]  # already printed
    assert [j.kind for j in library.jobs(3)] == ["ingredients"]  # no photo
    assert main(["zine-images", "--all"], library=library) == 0
    assert [j.kind for j in library.jobs(2)] == ["ingredients", "zine", "ingredients"]


def test_backfill_words_saves_only_real_cuisine_words(library, capsys):
    from burp.models import ImportedRecipe
    from burp.structure import WordAnswer

    library.add(
        ImportedRecipe(recipe=valid_recipe(title="Gnocchi di tofu"), content_source="caption")
    )
    library.add(ImportedRecipe(recipe=valid_recipe(title="Carbonara"), content_source="caption"))
    word = {"lingua": "ja", "parola": "もちもち", "traduzione": "consistenza gommosa"}
    client = FakeClient(WordAnswer(parola_cucina=word), WordAnswer(parola_cucina=None))
    assert main(["backfill-words"], client=client, library=library) == 0
    # The library lists the newest first: the carbonara was asked first and got nothing.
    assert library.get(1).recipe.parola_cucina is None
    assert library.get(2).recipe.parola_cucina.parola == "もちもち"
    assert "もちもち (ja)" in capsys.readouterr().out


def test_photos_from_reels_redo_never_replaces_a_photo_you_sent(
    library, capsys, monkeypatch, tmp_path
):
    from burp.ingest import SourcePost
    from burp.library import Media
    from burp.models import ImportedRecipe

    monkeypatch.setenv("BURP_PHOTO_FROM_REEL", "true")
    reel = tmp_path / "post.mp4"
    reel.write_bytes(b"video")
    fetched = []

    def fetch(url, cookies_file=None):
        fetched.append(url)
        return SourcePost(url=url, video_path=reel)

    monkeypatch.setattr("burp.cli.fetch_instagram", fetch)
    for n, source in ((1, "reel"), (2, "screenshot")):
        url = f"https://www.instagram.com/reel/r{n}/"
        library.add(ImportedRecipe(recipe=valid_recipe(source_url=url), content_source="caption"))
        library.set_media(n, Media(f"{n}/o.jpg", f"{n}/h.png", source, 0.9, "x", None, url))

    assert main(["photos-from-reels"], library=library) == 0
    assert fetched == []  # both have a photo
    assert main(["photos-from-reels", "--redo"], library=library) == 0
    assert fetched == ["https://www.instagram.com/reel/r1/"]
