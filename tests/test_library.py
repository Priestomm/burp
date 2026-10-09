import pytest

from burp.library import Library
from burp.models import ImportedRecipe
from tests.test_structure import ingredient, valid_recipe


def imported(**overrides) -> ImportedRecipe:
    return ImportedRecipe(recipe=valid_recipe(**overrides), content_source="caption")


@pytest.fixture
def filled(library):
    library.add(
        imported(
            title="Pasta e ceci",
            source_url="https://www.instagram.com/p/AAA/",
            ingredients=[
                ingredient("pasta", "80 g di pasta", 80, "g"),
                ingredient("ceci", "200 g di ceci", 200, "g"),
            ],
            tags={"cuisine": "italiana", "course": "primo", "diet": "vegan"},
        )
    )
    library.add(
        imported(
            title="Carbonara",
            source_url="https://www.instagram.com/reel/BBB/",
            ingredients=[
                ingredient("spaghetti", "200 g di spaghetti", 200, "g"),
                ingredient("pecorino romano", "50 g di pecorino", 50, "g"),
            ],
            tags={"cuisine": "italiana", "course": "primo", "diet": "neither"},
        )
    )
    library.add(
        imported(
            title="Curry di ceci",
            ingredients=[ingredient("ceci", "2 cans chickpeas", 2, "lattina")],
            tags={"cuisine": "indiana", "course": "piatto unico", "diet": "vegan"},
        )
    )
    return library


def titles(results) -> list[str]:
    return [r.recipe.title for r in results]


def test_add_and_get_round_trip(library):
    saved, created = library.add(imported(source_url="https://www.instagram.com/p/X/"))
    assert created
    assert library.get(saved.id) == saved
    assert saved.recipe.title == "Dal tadka"


def test_the_same_post_shared_twice_is_saved_once(library):
    first, created = library.add(imported(source_url="https://www.instagram.com/p/X/"))
    again, created_again = library.add(
        imported(title="Altro titolo", source_url="https://www.instagram.com/reel/X/?igsh=1")
    )
    assert created and not created_again
    assert again.id == first.id and again.recipe.title == "Dal tadka"
    assert len(library.search()) == 1


def test_find_by_url_uses_the_normalized_link(library):
    saved, _ = library.add(imported(source_url="https://www.instagram.com/reel/X/"))
    assert library.find_by_url("https://instagram.com/reels/X?igsh=abc") == saved
    assert library.find_by_url("https://www.instagram.com/p/Y/") is None


def test_recipes_without_a_link_are_never_deduplicated(library):
    library.add(imported())
    library.add(imported())
    assert len(library.search()) == 2


def test_search_without_filters_lists_everything_newest_first(filled):
    assert titles(filled.search()) == ["Curry di ceci", "Carbonara", "Pasta e ceci"]


def test_search_by_title_ignores_case_accents_and_word_order(filled):
    assert titles(filled.search(title="CECI pàsta")) == ["Pasta e ceci"]


def test_search_by_tag_matches_cuisine_course_or_diet(filled):
    assert titles(filled.search(tags=["Indiana"])) == ["Curry di ceci"]
    assert titles(filled.search(tags=["primo"])) == ["Carbonara", "Pasta e ceci"]
    assert titles(filled.search(tags=["vegana"])) == ["Curry di ceci", "Pasta e ceci"]
    assert titles(filled.search(tags=["primo", "vegan"])) == ["Pasta e ceci"]


def test_search_by_ingredient_uses_canonical_names(filled):
    assert titles(filled.search(ingredients=["chickpeas"])) == ["Curry di ceci", "Pasta e ceci"]
    assert titles(filled.search(ingredients=["pecorino"])) == ["Carbonara"]
    assert titles(filled.search(ingredients=["ceci", "pasta"])) == ["Pasta e ceci"]
    assert filled.search(ingredients=["guanciale"]) == []


def test_filters_combine(filled):
    assert titles(filled.search(title="curry", tags=["vegan"], ingredients=["ceci"])) == [
        "Curry di ceci"
    ]


def test_delete_removes_the_recipe_and_its_ingredients(filled):
    carbonara = filled.search(title="carbonara")[0]
    assert filled.delete(carbonara.id)
    assert filled.search(ingredients=["pecorino"]) == []
    assert not filled.delete(carbonara.id)


def test_library_persists_on_disk(tmp_path, catalog):
    path = tmp_path / "sub" / "burp.db"
    with Library(path, catalog) as lib:
        lib.add(imported())
    with Library(path, catalog) as lib:
        assert titles(lib.search()) == ["Dal tadka"]


def test_free_text_matches_title_tags_or_ingredients(filled):
    assert titles(filled.search(text="vegana ceci")) == ["Curry di ceci", "Pasta e ceci"]
    assert titles(filled.search(text="pecorino")) == ["Carbonara"]  # an ingredient only
    assert titles(filled.search(text="unico")) == ["Curry di ceci"]  # part of the course
    assert titles(filled.search(text="Curry chickpeas")) == ["Curry di ceci"]
    assert filled.search(text="carbonara vegana") == []


def test_quantities_written_by_the_user_or_accepted_by_eye(library):
    saved, _ = library.add(
        imported(
            ingredients=[
                ingredient("tofu", "400 g di tofu", 400, "g"),
                ingredient("cipollotto", "cipollotto"),
                ingredient("semi di sesamo", "semi di sesamo"),
            ]
        )
    )
    library.set_quantity(saved.id, 1, 1, None)
    updated = library.mark_by_eye(saved.id, [2])
    assert updated.imported.edits[1].quantity == 1
    assert updated.imported.edits[2].by_eye
    # The model's answer is untouched: the post still says nothing about cipollotto.
    assert updated.recipe.ingredients[1].quantity is None
    assert library.clear_edit(saved.id, 2).imported.edits.keys() == {1}


def test_editing_an_unknown_recipe_or_ingredient_fails(library):
    saved, _ = library.add(imported())
    with pytest.raises(KeyError):
        library.set_quantity(99, 0, 1, "g")
    with pytest.raises(IndexError):
        library.mark_by_eye(saved.id, [5])


def test_cooking_counts_every_time(library):
    saved, _ = library.add(imported())
    assert library.cooked(saved.id).count == 0
    library.cook(saved.id)
    cooked = library.cook(saved.id)
    assert cooked.count == 2 and cooked.last is not None
    with pytest.raises(KeyError):
        library.cook(99)


def test_a_library_from_before_the_title_split_is_upgraded(tmp_path, catalog):
    import json
    import sqlite3

    from burp.library import SCHEMA

    path = tmp_path / "old.db"
    old = imported(
        title="Gnocchi alla zucca definitivi",
        completeness={"status": "partial", "missing": ["quantità di tuorli", "quantità di tuorlo"]},
    ).model_dump(mode="json")
    for key in ("nome_riga_1", "nome_riga_2", "descrittore"):
        del old["recipe"][key]
    del old["edits"]
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    row = ("Gnocchi", "gnocchi", "vegan", json.dumps(old), "2026-09-27T15:32:38+00:00")
    conn.execute(
        "INSERT INTO recipes (title, title_norm, diet, data, created_at) VALUES (?, ?, ?, ?, ?)",
        row,
    )
    conn.commit()
    conn.close()

    with Library(path, catalog) as lib:
        [saved] = lib.search()
        assert saved.recipe.nome_riga_1 == "Gnocchi alla zucca definitivi"
        assert saved.recipe.completeness.missing == ["quantità di tuorli"]
        assert lib.cooked(saved.id).count == 0  # the new table exists
    with Library(path, catalog) as lib:  # opening again changes nothing
        assert lib.search()[0].recipe.completeness.missing == ["quantità di tuorli"]


def test_a_drawing_goes_with_its_recipe(library):
    from burp.models import Stroke

    saved, _ = library.add(imported())
    strokes = [Stroke(anchor="step-0", d="M1 2L3 4")]
    assert library.drawing(saved.id) == []
    library.set_drawing(saved.id, strokes)
    assert library.drawing(saved.id) == strokes
    library.set_drawing(saved.id, [])
    assert library.drawing(saved.id) == []
    library.set_drawing(saved.id, strokes)
    library.delete(saved.id)
    assert library.drawing(saved.id) == []  # ON DELETE CASCADE
    with pytest.raises(KeyError):
        library.set_drawing(99, strokes)
