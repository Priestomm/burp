"""Runs the four caption fixtures against the real Anthropic API.

Opt-in (costs money): `uv run pytest -m live` with ANTHROPIC_API_KEY set. These check the
behaviour that offline tests cannot: that the model really follows the schema and the rules.
"""

import os
import re
from pathlib import Path

import anthropic
import pytest

from burp.config import DEFAULT_MODEL
from burp.extract import is_sufficient
from burp.structure import structure_recipe

CAPTIONS = Path(__file__).parent / "fixtures" / "captions"
ITALIAN = re.compile(r"\b(il|la|le|gli|di|e|con|per|nel|nella|fino|aggiungi|cuoci)\b")
ENGLISH = re.compile(r"\b(the|and|with|until|add|cook|stir|heat)\b", re.IGNORECASE)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set"),
]


@pytest.fixture(scope="module")
def structure(catalog):
    client = anthropic.Anthropic()
    model = os.environ.get("BURP_MODEL", DEFAULT_MODEL)

    def run(name: str):
        text = (CAPTIONS / f"{name}.txt").read_text()
        return structure_recipe(text, catalog, client, model)

    return run


def test_complete_caption_is_complete_and_not_vegetarian(structure):
    recipe = structure("completa")
    assert recipe.completeness.status == "complete", recipe.completeness.missing
    assert recipe.tags.diet == "neither"
    assert recipe.tags.course == "primo"
    assert recipe.servings == 2 and recipe.time_minutes == 25
    assert "guanciale" in [i.canonical_name for i in recipe.ingredients]


def test_missing_quantities_are_not_invented(structure):
    recipe = structure("quantita_mancanti")
    assert recipe.completeness.status == "partial"
    pasta = next(i for i in recipe.ingredients if "pasta" in i.canonical_name)
    assert pasta.quantity is None
    assert any("pasta" in item for item in recipe.completeness.missing)


def test_english_caption_is_translated_to_italian(structure):
    recipe = structure("inglese")
    steps = " ".join(recipe.steps)
    assert ITALIAN.search(steps) and not ENGLISH.search(steps), steps
    assert not ENGLISH.search(recipe.title), recipe.title
    assert recipe.tags.diet == "vegan"
    assert recipe.servings == 4
    assert "ceci" in [i.canonical_name for i in recipe.ingredients]


def test_empty_caption_is_rejected_before_any_api_call():
    ok, _ = is_sufficient((CAPTIONS / "vuota.txt").read_text())
    assert not ok
