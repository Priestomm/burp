import json
from pathlib import Path

from mappetito_pipeline.sources.wikidata import build_query, parse_response

FIXTURE = Path(__file__).parent / "fixtures" / "wikidata_response.json"


def test_parse_groups_rows_by_dish():
    dishes = parse_response(json.loads(FIXTURE.read_text()))
    assert [d.qid for d in dishes] == ["Q1234501", "Q1234502", "Q1234503"]
    assert dishes[0].ingredient_names_en == ["chickpea", "pasta"]


def test_parse_handles_missing_optional_fields():
    dal = parse_response(json.loads(FIXTURE.read_text()))[1]
    assert dal.name_it is None
    assert dal.ingredient_names_en == []


def test_parse_zero_pads_country_code():
    assert parse_response(json.loads(FIXTURE.read_text()))[2].country_code == "004"


def test_query_uses_country_of_origin_property():
    query = build_query(limit=10)
    assert "wdt:P495" in query and "LIMIT 10" in query
