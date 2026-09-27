"""Runs the four caption fixtures against the real Anthropic API.

Opt-in (costs money): `uv run pytest -m live` with ANTHROPIC_API_KEY set. These check the
behaviour that offline tests cannot: that the model really follows the schema and the rules.
"""

import os
from pathlib import Path

import anthropic
import pytest

from burp.config import DEFAULT_MODEL
from burp.ingest.content import is_sufficient
from burp.ingest.reconcile import reconcile
from burp.ingest.structure import structure_recipe

CAPTIONS = Path(__file__).parent / "fixtures" / "captions"

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set"),
]


@pytest.fixture(scope="module")
def structure(ingredients):
    client = anthropic.Anthropic()
    model = os.environ.get("BURP_MODEL", DEFAULT_MODEL)

    def run(name: str):
        text = (CAPTIONS / f"{name}.txt").read_text()
        extracted = structure_recipe(text, ingredients, client, model)
        return extracted, reconcile(extracted, ingredients)

    return run


def test_vegan_dal_is_india_and_vegan(structure):
    extracted, result = structure("vegan_dal")
    assert extracted.origin.country_iso2 == "IN"
    assert extracted.diet == "vegan" and extracted.veganized_version is None
    assert result.draft.country_code == "356"
    assert result.diet == "vegan"


def test_carbonara_is_italian_non_vegetarian_and_gets_veganized(structure):
    extracted, result = structure("carbonara")
    assert extracted.origin.country_iso2 == "IT"
    assert extracted.diet == "neither"
    assert extracted.veganized_version and extracted.veganized_version.substitutions
    assert result.draft.adaptation is not None
    assert result.diet in {"vegan", "vegetarian"}  # the published variant has no meat


def test_ambiguous_fusion_is_not_given_a_confident_country(structure):
    extracted, result = structure("fusion_bibimbap_tacos")
    assert extracted.origin.confidence < 0.6
    assert result.status == "needs_review"


def test_emoji_only_caption_is_rejected_before_any_api_call():
    ok, _ = is_sufficient((CAPTIONS / "emoji_only.txt").read_text())
    assert not ok
