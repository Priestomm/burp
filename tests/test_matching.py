import pytest

from burp.matching import SynonymIndex, normalize_name


@pytest.fixture(scope="module")
def index(ingredients):
    return SynonymIndex(ingredients)


def test_normalize_strips_accents_case_and_punctuation():
    assert normalize_name("  Crème-Fraîche! ") == "creme fraiche"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("tofu", "tofu"),
        ("olive_oil", "olive_oil"),
        ("olio d'oliva", "olive_oil"),
        ("parmesan", "parmigiano_reggiano"),
        ("nam pla", "fish_sauce"),
    ],
)
def test_exact_names_and_synonyms_resolve(index, text, expected):
    assert index.resolve(text) == expected


def test_falls_back_to_a_known_name_inside_the_text(index):
    assert index.resolve("2 cucchiai di olio d'oliva extravergine") == "olive_oil"


def test_first_candidate_that_matches_wins(index):
    assert index.resolve("something unknown", "150 g tofu") == "tofu"


def test_unknown_ingredient_is_none(index):
    assert index.resolve("unobtainium") is None
