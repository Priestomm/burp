from burp.models import ImportedRecipe, IngredientEdit
from burp.view import ingredient_views, missing_names
from tests.test_structure import ingredient, valid_recipe


def imported(edits: dict[int, IngredientEdit] | None = None) -> ImportedRecipe:
    recipe = valid_recipe(
        ingredients=[
            ingredient("tofu", "400g tofu vellutato", 400, "g"),
            ingredient("olio di sesamo", "3 cucchiai olio di sesamo", 3, "cucchiaio"),
            ingredient("limone", "Succo di limone qb", unit="q.b."),
            ingredient("cipollotto", "cipollotto per decorare"),
            ingredient("semi di sesamo", "semi di sesamo per decorare"),
            ingredient("ceci", "2 × 15-oz cans chickpeas", 2, "lattina da 15 oz"),
        ]
    )
    return ImportedRecipe(recipe=recipe, content_source="caption", edits=edits or {})


def by_name(views):
    return {view.name: view for view in views}


def test_status_and_base_unit_of_each_quantity():
    views = by_name(ingredient_views(imported()))
    assert (views["tofu"].status, views["tofu"].base_unit, views["tofu"].base_quantity) == (
        "given",
        "g",
        400,
    )
    assert (views["olio di sesamo"].base_unit, views["olio di sesamo"].base_quantity) == (
        "tsp",
        9,
    )
    assert views["limone"].status == "to_taste"
    assert views["cipollotto"].status == "missing"
    # Shown as written, but not scalable.
    assert views["ceci"].status == "given" and views["ceci"].base_unit is None


def test_user_edits_fill_or_accept_missing_quantities():
    edits = {3: IngredientEdit(quantity=1, unit=None), 4: IngredientEdit(by_eye=True)}
    views = by_name(ingredient_views(imported(edits)))
    assert views["cipollotto"].status == "given"
    assert views["cipollotto"].edited and views["cipollotto"].base_unit == "piece"
    assert views["semi di sesamo"].status == "by_eye"
    assert not views["tofu"].edited


def test_missing_names():
    assert missing_names(imported()) == ["cipollotto", "semi di sesamo"]
    assert missing_names(imported({4: IngredientEdit(by_eye=True)})) == ["cipollotto"]
