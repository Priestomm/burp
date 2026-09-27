import pytest

HIDDEN_ANIMAL = [
    "fish_sauce",
    "anchovy",
    "worcestershire_sauce",
    "meat_broth",
    "fish_broth",
    "gelatin",
    "lard",
    "dashi_katsuobushi",
    "parmigiano_reggiano",
    "grana_padano",
    "pecorino_romano",
]


@pytest.mark.parametrize("ingredient_id", HIDDEN_ANIMAL)
def test_hidden_animal_ingredient_is_flagged_and_explained(ingredients, ingredient_id):
    ingredient = ingredients[ingredient_id]
    assert not ingredient.is_vegetarian
    assert not ingredient.is_vegan
    assert ingredient.notes, f"{ingredient_id} needs a note explaining its animal origin"


@pytest.mark.parametrize("synonym", ["parmesan", "nam pla", "bonito flakes", "bouillon cube"])
def test_common_synonyms_resolve_to_animal_ingredients(ingredients, synonym):
    owners = [i for i in ingredients.values() if synonym in i.synonyms_en]
    assert owners and all(not i.is_vegetarian for i in owners)


def test_kombu_dashi_alternative_is_vegan(ingredients):
    assert ingredients["kombu"].is_vegan
