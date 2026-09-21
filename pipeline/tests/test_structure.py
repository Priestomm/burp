from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from mappetito_pipeline.ingest.structure import (
    ExtractedRecipe,
    StructuringError,
    structure_recipe,
)


def valid_recipe(**overrides) -> ExtractedRecipe:
    data = {
        "title": "Dal tadka",
        "ingredients": [
            {"canonical_name": "red_lentils", "original_text": "150 g lenticchie rosse"}
        ],
        "steps": ["Cuoci le lenticchie."],
        "origin": {
            "country_iso2": "IN",
            "cuisine": "Indian",
            "confidence": 0.95,
            "reasoning": "Classic Indian dal.",
        },
        "diet": "vegan",
    } | overrides
    return ExtractedRecipe.model_validate(data)


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
        ExtractedRecipe.model_validate({})
    except ValidationError as error:
        return error
    raise AssertionError


def test_vegan_recipe_must_not_carry_a_veganized_version():
    with pytest.raises(ValidationError, match="must be null"):
        valid_recipe(veganized_version={"substitutions": []})


def test_non_vegan_recipe_requires_a_veganized_version():
    with pytest.raises(ValidationError, match="required"):
        valid_recipe(diet="neither")


def test_confidence_is_bounded():
    with pytest.raises(ValidationError):
        valid_recipe(
            origin={"country_iso2": "IT", "cuisine": "x", "confidence": 1.5, "reasoning": "x"}
        )


def test_returns_the_parsed_recipe_and_sets_source_url(ingredients):
    client = FakeClient(valid_recipe())
    recipe = structure_recipe(
        "text", ingredients, client, "m", source_url="https://www.instagram.com/p/x/"
    )
    assert recipe.source_url == "https://www.instagram.com/p/x/"
    call = client.calls[0]
    assert call["output_format"] is ExtractedRecipe
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "red_lentils" in call["system"][0]["text"]


def test_invalid_output_is_retried_with_the_error_in_the_prompt(ingredients):
    client = FakeClient(invalid_json_error(), valid_recipe())
    recipe = structure_recipe("text", ingredients, client, "m")
    assert recipe.title == "Dal tadka"
    assert len(client.calls) == 2
    assert "previous answer was rejected" in client.calls[1]["messages"][0]["content"]
    assert "previous answer" not in client.calls[0]["messages"][0]["content"]


def test_gives_up_after_max_attempts(ingredients):
    client = FakeClient(invalid_json_error(), invalid_json_error())
    with pytest.raises(StructuringError, match="2 attempts"):
        structure_recipe("text", ingredients, client, "m")
    assert len(client.calls) == 2
