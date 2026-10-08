from types import SimpleNamespace

from burp.fill import ClaudeFiller, Fill, QuantityGuess, describe, to_enrichment
from burp.models import Enrichment, Estimate, ImportedRecipe, IngredientEdit
from burp.view import ingredient_views
from tests.test_structure import ingredient, valid_recipe


def imported(**overrides) -> ImportedRecipe:
    recipe = valid_recipe(
        title="Gnocchi di tofu gommosi glassati",
        servings=3,
        ingredients=[
            ingredient("tofu", "400g tofu vellutato", 400, "g"),
            ingredient("limone", "Succo di limone qb", unit="q.b."),
            ingredient("cipollotto", "cipollotto per decorare"),
            ingredient("semi di sesamo", "semi di sesamo per decorare"),
        ],
        steps=["Unire tofu e farina.", "Cuocere in acqua."],
    )
    return ImportedRecipe(recipe=recipe, content_source="caption", **overrides)


def fill(**overrides) -> Fill:
    data = {
        "quantities": [
            {"index": 2, "quantity": 1, "unit": None, "reason": "guarnizione per 3"},
            {"index": 3, "quantity": 1, "unit": "cucchiaino", "reason": "una spolverata"},
        ],
        "servings": None,
        "time_minutes": 30,
        "steps": ["Unisci tofu e farina e mescola.", "  ", "Cuoci in acqua bollente."],
        "steps_note": None,
    } | overrides
    return Fill.model_validate(data)


def test_the_model_sees_numbered_ingredients_with_question_marks_where_unknown():
    text = describe(imported())
    assert "Porzioni: 3" in text and "Tempo: non noto" in text
    assert "0. tofu: 400 g (400g tofu vellutato)" in text
    assert "1. limone: q.b." in text
    assert "2. cipollotto: ? (cipollotto per decorare)" in text
    assert "- Unire tofu e farina." in text


def test_only_real_gaps_are_kept():
    guesses = fill(
        quantities=[
            {"index": 0, "quantity": 999, "unit": "g", "reason": "no"},  # the post says 400 g
            {"index": 2, "quantity": 1, "unit": None, "reason": "guarnizione per 3"},
            {"index": 9, "quantity": 1, "unit": None, "reason": "no such ingredient"},
        ],
        servings=4,  # the post says 3
    )
    enrichment = to_enrichment(imported(), guesses, "claude-haiku-4-5")
    assert enrichment.quantities.keys() == {2}
    assert enrichment.servings is None and enrichment.time_minutes == 30
    assert enrichment.steps == ["Unisci tofu e farina e mescola.", "Cuoci in acqua bollente."]


def test_quantities_already_accepted_by_eye_are_left_alone():
    recipe = imported(edits={3: IngredientEdit(by_eye=True)})
    assert to_enrichment(recipe, fill(), "m").quantities.keys() == {2}


def test_estimates_show_as_estimates_and_the_user_wins():
    enrichment = Enrichment(
        model="m",
        created_at="2026-10-08T12:00:00+00:00",
        quantities={2: Estimate(quantity=1, unit=None, reason="guarnizione per 3")},
    )
    views = ingredient_views(imported(enrichment=enrichment))
    assert (views[2].status, views[2].quantity, views[2].estimate_reason) == (
        "estimated",
        1,
        "guarnizione per 3",
    )
    assert views[2].base_unit == "piece"
    assert views[3].status == "missing"
    written = ingredient_views(
        imported(enrichment=enrichment, edits={2: IngredientEdit(quantity=2, unit=None)})
    )
    assert (written[2].status, written[2].quantity, written[2].estimate_reason) == (
        "given",
        2,
        None,
    )


def test_claude_filler_asks_once_with_the_recipe():
    calls = []

    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(parsed_output=fill(), stop_reason="end_turn")

    client = SimpleNamespace(messages=SimpleNamespace(parse=parse))
    enrichment = ClaudeFiller(client, "claude-haiku-4-5").fill(imported())
    assert enrichment.model == "claude-haiku-4-5" and enrichment.quantities[3].unit == "cucchiaino"
    assert calls[0]["output_format"] is Fill
    assert "Non scrivere le quantità nei passaggi" in calls[0]["system"].replace("\n", " ")
    assert "cipollotto: ?" in calls[0]["messages"][0]["content"]


def test_guess_reason_is_short():
    guess = QuantityGuess(index=2, quantity=1, unit=None, reason="x" * 200)
    enrichment = to_enrichment(imported(), fill(quantities=[guess.model_dump()]), "m")
    assert len(enrichment.quantities[2].reason) == 80


def test_the_word_null_as_a_unit_means_no_unit():
    # Seen live with Haiku: {"unit": "null"} for 2 cipollotti.
    guesses = fill(quantities=[{"index": 2, "quantity": 2, "unit": "null", "reason": "x"}])
    assert to_enrichment(imported(), guesses, "m").quantities[2].unit is None


def test_a_new_estimate_starts_from_the_post_not_the_old_estimate():
    old = Enrichment(
        model="m",
        created_at="2026-10-08T12:00:00+00:00",
        quantities={2: Estimate(quantity=5, unit=None, reason="vecchia")},
    )
    recipe = imported(enrichment=old)
    assert "2. cipollotto: 5" in describe(recipe)  # what the page shows
    enrichment = to_enrichment(recipe, fill(), "m")
    assert enrichment.quantities.keys() == {2, 3}  # both still count as gaps

    calls = []

    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(parsed_output=fill(), stop_reason="end_turn")

    client = SimpleNamespace(messages=SimpleNamespace(parse=parse))
    ClaudeFiller(client, "m").fill(recipe)
    assert "cipollotto: ?" in calls[0]["messages"][0]["content"]


def test_hidden_estimates_are_not_shown():
    hidden = Enrichment(
        model="m",
        created_at="2026-10-08T12:00:00+00:00",
        quantities={2: Estimate(quantity=1, unit=None, reason="x")},
        active=False,
    )
    assert ingredient_views(imported(enrichment=hidden))[2].status == "missing"
