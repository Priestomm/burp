import pytest

from mappetito_pipeline.loader import load_ingredients
from mappetito_pipeline.models import RecipeDraft, RecipeIngredient


@pytest.fixture(scope="session")
def ingredients():
    return load_ingredients()


@pytest.fixture
def make_draft():
    def _make(*ingredient_ids: str) -> RecipeDraft:
        return RecipeDraft(
            id="test-dish",
            name="Test dish",
            name_it="Piatto di prova",
            country_code="380",
            ingredients=[RecipeIngredient(ingredient_id=i, is_core=True) for i in ingredient_ids],
            steps=["Cook."],
            source="test",
            license="CC0",
        )

    return _make
