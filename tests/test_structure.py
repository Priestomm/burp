from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from burp.models import Recipe
from burp.structure import StructuringError, finalize, structure_recipe


def valid_recipe(**overrides) -> Recipe:
    data = {
        "title": "Dal tadka",
        "ingredients": [
            {
                "canonical_name": "lenticchie rosse",
                "original_text": "150 g di lenticchie rosse",
                "quantity": 150,
                "unit": "g",
            }
        ],
        "steps": ["Cuoci le lenticchie."],
        "tags": {"cuisine": "indiana", "course": "piatto unico", "diet": "vegan"},
        "completeness": {"status": "complete", "missing": []},
    } | overrides
    return Recipe.model_validate(data)


def ingredient(name: str, text: str, quantity=None, unit=None) -> dict:
    return {"canonical_name": name, "original_text": text, "quantity": quantity, "unit": unit}


class FakeClient:
    """Stands in for anthropic.Anthropic: each queued item is returned or raised in turn."""

    def __init__(self, *outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(parsed_output=outcome, stop_reason="end_turn")


def invalid_json_error() -> ValidationError:
    try:
        Recipe.model_validate({})
    except ValidationError as error:
        return error
    raise AssertionError


def test_partial_recipe_must_say_what_is_missing():
    with pytest.raises(ValidationError, match="must list what is missing"):
        valid_recipe(completeness={"status": "partial", "missing": []})


def test_complete_recipe_cannot_list_missing_items():
    with pytest.raises(ValidationError, match="must be 'partial'"):
        valid_recipe(completeness={"status": "complete", "missing": ["tempo"]})


def test_diet_and_course_are_closed_sets():
    with pytest.raises(ValidationError):
        valid_recipe(tags={"diet": "pescatarian"})
    with pytest.raises(ValidationError):
        valid_recipe(tags={"diet": "vegan", "course": "merenda"})


def test_returns_the_parsed_recipe_with_source_and_author(catalog):
    client = FakeClient(valid_recipe(author_handle="someone_else"))
    recipe = structure_recipe(
        "text",
        catalog,
        client,
        "m",
        source_url="https://www.instagram.com/p/x/",
        author_handle="cucina.di.anna",
    )
    assert recipe.source_url == "https://www.instagram.com/p/x/"
    assert recipe.author_handle == "cucina.di.anna"  # the post metadata wins over the model
    call = client.calls[0]
    assert call["output_format"] is Recipe
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "lenticchie rosse [vegan]" in call["system"][0]["text"]
    assert "in italiano" in call["system"][0]["text"]


def test_invalid_output_is_retried_with_the_error_in_the_prompt(catalog):
    client = FakeClient(invalid_json_error(), valid_recipe())
    recipe = structure_recipe("text", catalog, client, "m")
    assert recipe.title == "Dal tadka"
    assert len(client.calls) == 2
    assert "risposta precedente" in client.calls[1]["messages"][0]["content"]
    assert "risposta precedente" not in client.calls[0]["messages"][0]["content"]


def test_gives_up_after_max_attempts(catalog):
    client = FakeClient(invalid_json_error(), invalid_json_error())
    with pytest.raises(StructuringError, match="2 attempts"):
        structure_recipe("text", catalog, client, "m")
    assert len(client.calls) == 2


def test_canonical_names_come_from_the_catalog(catalog):
    recipe = valid_recipe(
        ingredients=[
            ingredient("Chickpeas", "1 can chickpeas", 1, "lattina"),
            ingredient("pomodori", "2 pomodori", 2),
            ingredient("Mezze Maniche", "mezze maniche", 200, "g"),
        ]
    )
    names = [i.canonical_name for i in finalize(recipe, catalog).ingredients]
    assert names == ["ceci", "pomodoro", "mezze maniche"]


def test_missing_quantities_make_the_recipe_partial_even_if_the_model_says_complete(catalog):
    recipe = valid_recipe(
        ingredients=[
            ingredient("pasta", "pasta corta"),
            ingredient("sale", "sale", unit="q.b."),
            ingredient("pepe nero", "pepe a piacere"),
            ingredient("zucchina", "2 zucchine", 2),
        ]
    )
    completeness = finalize(recipe, catalog).completeness
    assert completeness.status == "partial"
    assert completeness.missing == ["quantità di pasta"]


def test_missing_items_already_listed_by_the_model_are_not_repeated(catalog):
    recipe = valid_recipe(
        ingredients=[ingredient("pasta", "pasta corta")],
        steps=[],
        completeness={"status": "partial", "missing": ["quantità della pasta", "procedimento"]},
    )
    assert finalize(recipe, catalog).completeness.missing == [
        "quantità della pasta",
        "procedimento",
    ]


def test_missing_steps_make_the_recipe_partial(catalog):
    completeness = finalize(valid_recipe(steps=[]), catalog).completeness
    assert completeness.missing == ["procedimento"]


def test_diet_is_downgraded_when_a_known_ingredient_contradicts_it(catalog, caplog):
    recipe = valid_recipe(
        ingredients=[ingredient("Pecorino Romano", "50 g di pecorino", 50, "g")],
        tags={"cuisine": "italiana", "course": "primo", "diet": "vegetarian"},
    )
    assert finalize(recipe, catalog).tags.diet == "neither"
    assert "model said 'vegetarian'" in caplog.text


def test_diet_is_never_upgraded_from_the_catalog(catalog):
    # Unknown ingredients may be animal: only the model can say a dish is not vegan.
    recipe = valid_recipe(
        ingredients=[ingredient("ceci", "200 g di ceci", 200, "g")],
        tags={"diet": "neither"},
    )
    assert finalize(recipe, catalog).tags.diet == "neither"
