import pytest

from burp.catalog import SynonymIndex, load_ingredients
from burp.library import Library


@pytest.fixture(scope="session")
def ingredients():
    return load_ingredients()


@pytest.fixture(scope="session")
def catalog(ingredients):
    return SynonymIndex(ingredients)


@pytest.fixture
def library(catalog):
    with Library(":memory:", catalog) as lib:
        yield lib
