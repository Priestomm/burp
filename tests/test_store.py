from burp.models import ImportedRecipe
from burp.store import load_all, save, slugify
from tests.test_structure import valid_recipe


def test_save_and_load_round_trip(tmp_path):
    imported = ImportedRecipe(
        recipe=valid_recipe(), content_source="transcript", content_reason="caption: empty"
    )
    path = save(imported, tmp_path)
    assert path.name == "dal-tadka.json"
    assert load_all(tmp_path) == [imported]


def test_load_all_of_a_missing_directory_is_empty(tmp_path):
    assert load_all(tmp_path / "nope") == []


def test_slugify_strips_accents():
    assert slugify("Pasta è ceci!") == "pasta-e-ceci"
