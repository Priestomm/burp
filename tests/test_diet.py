import pytest
from pydantic import ValidationError

from burp.diet import (
    NonVegetarianIngredientError,
    UnknownIngredientError,
    compute_diet,
    to_recipe,
)
from burp.models import Ingredient


def test_all_vegan_ingredients_give_vegan(ingredients, make_draft):
    assert compute_diet(make_draft("chickpeas", "olive_oil", "garlic"), ingredients) == "vegan"


def test_one_non_vegan_vegetarian_ingredient_gives_vegetarian(ingredients, make_draft):
    assert compute_diet(make_draft("chickpeas", "egg"), ingredients) == "vegetarian"


def test_fish_sauce_is_rejected(ingredients, make_draft):
    draft = make_draft("tofu", "fish_sauce")
    with pytest.raises(NonVegetarianIngredientError, match="fish_sauce"):
        compute_diet(draft, ingredients)


def test_unknown_ingredient_is_rejected(ingredients, make_draft):
    with pytest.raises(UnknownIngredientError, match="unobtainium"):
        compute_diet(make_draft("unobtainium"), ingredients)


def test_to_recipe_sets_computed_diet(ingredients, make_draft):
    assert to_recipe(make_draft("paneer", "spinach"), ingredients).diet == "vegetarian"


def test_draft_cannot_declare_diet(make_draft):
    data = make_draft("tofu").model_dump() | {"diet": "vegan"}
    from burp.models import RecipeDraft

    with pytest.raises(ValidationError):
        RecipeDraft(**data)


def test_ingredient_cannot_be_vegan_but_not_vegetarian():
    with pytest.raises(ValidationError):
        Ingredient(id="x", name_en="x", name_it="x", is_vegetarian=False, is_vegan=True)
