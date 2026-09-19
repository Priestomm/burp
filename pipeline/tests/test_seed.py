import json

from build import build
from mappetito_pipeline.loader import load_recipe_drafts

SEED_COUNTRIES = {"380", "392", "484", "504", "356"}


def test_seed_recipes_validate_and_have_ids():
    drafts = load_recipe_drafts()
    assert len(drafts) == 10


def test_seed_covers_five_countries_with_two_dishes_each():
    drafts = load_recipe_drafts()
    counts: dict[str, int] = {}
    for draft in drafts:
        counts[draft.country_code] = counts.get(draft.country_code, 0) + 1
    assert counts == dict.fromkeys(SEED_COUNTRIES, 2)


def test_seed_is_marked_as_sample():
    assert {d.source for d in load_recipe_drafts()} == {"sample"}


def test_seed_has_at_least_one_adaptation():
    assert any(d.adaptation is not None for d in load_recipe_drafts())


def test_build_writes_json_with_computed_diet(tmp_path):
    _, recipes = build(tmp_path)
    written = json.loads((tmp_path / "recipes.json").read_text())
    assert len(written) == len(recipes) == 10
    diets = {r["id"]: r["diet"] for r in written}
    assert diets["it-pasta-e-ceci"] == "vegan"
    assert diets["it-pasta-alla-norma"] == "vegetarian"
    assert diets["mx-huevos-rancheros"] == "vegetarian"
    assert diets["in-palak-paneer"] == "vegetarian"
    assert (tmp_path / "ingredients.json").exists()
