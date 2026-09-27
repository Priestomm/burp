from pathlib import Path

import pytest

from burp.cli import main
from tests.test_structure import FakeClient, ingredient, valid_recipe

CAPTIONS = Path(__file__).parent / "fixtures" / "captions"
URL = "https://www.instagram.com/p/abc/"


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr("burp.cli.load_env", lambda: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")


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
