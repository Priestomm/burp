import pytest

from burp.catalog import SynonymIndex, load_ingredients


@pytest.fixture(scope="session")
def ingredients():
    return load_ingredients()


@pytest.fixture(scope="session")
def catalog(ingredients):
    return SynonymIndex(ingredients)
