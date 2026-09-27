import pytest

from burp.reconcile import country_numeric, reconcile, slugify
from burp.store import Provenance
from burp.structure import ExtractedRecipe


def ing(name, text=None, quantity=None, unit=None):
    return {
        "canonical_name": name,
        "original_text": text or name,
        "quantity": quantity,
        "unit": unit,
    }


def recipe(**overrides) -> ExtractedRecipe:
    data = {
        "title": "Dal tadka",
        "ingredients": [
            ing("red_lentils", "150 g lenticchie rosse", 150, "g"),
            ing("onion", "1 cipolla", 1, "piece"),
            ing("salt", "sale q.b."),
        ],
        "steps": ["Cuoci le lenticchie.", "Aggiungi il soffritto."],
        "origin": {
            "country_iso2": "IN",
            "cuisine": "Indian",
            "confidence": 0.95,
            "reasoning": "Classic Indian dal.",
        },
        "diet": "vegan",
    } | overrides
    return ExtractedRecipe.model_validate(data)


def carbonara(**overrides) -> ExtractedRecipe:
    defaults = {
        "title": "Carbonara",
        "ingredients": [
            ing("pasta", "200 g di spaghetti", 200, "g"),
            ing("guanciale", "100 g di guanciale", 100, "g"),
            ing("egg", "3 tuorli", 3, "piece"),
            ing("pecorino_romano", "50 g di pecorino romano", 50, "g"),
            ing("black_pepper", "pepe nero"),
        ],
        "origin": {
            "country_iso2": "IT",
            "cuisine": "Roman",
            "confidence": 0.98,
            "reasoning": "Traditional Roman dish.",
        },
        "diet": "neither",
        "veganized_version": {
            "substitutions": [
                {"original": "guanciale", "replacement": "tofu"},
                {"original": "pecorino_romano", "replacement": "miso"},
            ],
            "notes": "Smoky tofu stands in for the cured pork.",
        },
    }
    return recipe(**(defaults | overrides))


def test_country_numeric_maps_iso2_to_the_apps_numeric_codes():
    assert country_numeric("IT") == "380"
    assert country_numeric("in") == "356"
    assert country_numeric("MX") == "484"
    assert country_numeric("ZZ") is None


def test_slugify_is_ascii_and_id_safe():
    assert slugify("Pasta e Ceci — ricetta nonna!") == "pasta-e-ceci-ricetta-nonna"
    assert slugify("!!!") == "recipe"


def test_clean_vegan_recipe_is_ready(ingredients):
    result = reconcile(recipe(), ingredients, Provenance(source="caption"))
    assert result.status == "ready" and result.issues == []
    assert result.diet == "vegan"
    assert result.id == "in-dal-tadka"
    draft = result.draft
    assert draft.country_code == "356"
    assert [i.ingredient_id for i in draft.ingredients] == ["red_lentils", "onion", "salt"]
    assert [i.is_core for i in draft.ingredients] == [True, True, False]
    assert draft.adaptation is None


def test_ingredient_resolves_through_synonyms_when_name_is_not_an_id(ingredients):
    extracted = recipe(
        ingredients=[ing("parmesan", "50 g parmesan", 50, "g")],
        diet="vegetarian",
        veganized_version={"substitutions": []},
    )
    result = reconcile(extracted, ingredients)
    assert result.draft.ingredients[0].ingredient_id == "parmigiano_reggiano"


def test_meat_dish_is_veganized_into_an_adaptation(ingredients):
    result = reconcile(carbonara(), ingredients)
    assert result.status == "ready", result.issues
    ids = [i.ingredient_id for i in result.draft.ingredients]
    assert "tofu" in ids and "miso" in ids
    assert "pecorino_romano" not in ids
    adaptation = result.draft.adaptation
    assert adaptation.original_dish == "Carbonara"
    assert "guanciale -> tofu" in adaptation.changes
    assert result.diet == "vegetarian"  # eggs stay, so vegetarian rather than vegan


def test_non_vegetarian_dish_without_working_substitutions_needs_review(ingredients):
    result = reconcile(carbonara(veganized_version={"substitutions": []}), ingredients)
    assert result.status == "needs_review"
    assert any("no substitutions" in issue for issue in result.issues)


def test_low_confidence_country_needs_review_instead_of_inventing(ingredients):
    extracted = recipe(
        origin={
            "country_iso2": "KR",
            "cuisine": "Korean-Mexican fusion",
            "confidence": 0.4,
            "reasoning": "Fusion of two cuisines.",
        }
    )
    result = reconcile(extracted, ingredients)
    assert result.status == "needs_review"
    assert any("confidence 0.40" in issue for issue in result.issues)
    assert result.draft is not None  # kept for a human to confirm the country


def test_unresolved_ingredient_needs_review(ingredients):
    extracted = recipe(ingredients=[ing("dragon_fruit", "1 dragon fruit", 1, "piece")])
    result = reconcile(extracted, ingredients)
    assert result.status == "needs_review"
    assert result.issues == ["unresolved ingredient 'dragon_fruit'"]
    assert result.diet is None


def test_diet_declared_vegan_but_ingredients_say_vegetarian_is_flagged(ingredients):
    extracted = recipe(ingredients=[ing("egg", "2 uova", 2, "piece")])
    result = reconcile(extracted, ingredients)
    assert result.status == "needs_review"
    assert result.diet == "vegetarian"
    assert any("declared 'vegan'" in issue for issue in result.issues)


def test_unknown_country_code_needs_review_without_a_draft(ingredients):
    extracted = recipe(
        origin={"country_iso2": "ZZ", "cuisine": "?", "confidence": 0.9, "reasoning": "?"}
    )
    result = reconcile(extracted, ingredients)
    assert result.status == "needs_review" and result.draft is None
    assert result.id == "xx-dal-tadka"


@pytest.mark.parametrize("quantity", [0, -1, None])
def test_non_positive_quantity_becomes_to_taste(ingredients, quantity):
    result = reconcile(recipe(ingredients=[ing("salt", "sale", quantity, "g")]), ingredients)
    item = result.draft.ingredients[0]
    assert item.quantity is None and item.unit is None
