"""Wikidata source: dishes with their country of origin (P495) and optional ingredients.

Wikidata data is CC0. The output is raw candidate data: it still has to be curated
(ingredient mapping, diet check, steps) before it becomes a `Recipe`.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
# Wikimedia asks for a descriptive User-Agent with contact info on all API requests.
# TODO: add the project URL or a contact address before running against the live endpoint.
USER_AGENT = "mappetito-pipeline/0.1"

# Q746549 = dish, P495 = country of origin, P299 = ISO 3166-1 numeric code,
# P527 = has part(s), used here as a rough "ingredient" relation.
DISHES_QUERY = """
SELECT ?dish ?nameEn ?nameIt ?countryIso ?ingredient ?ingredientNameEn WHERE {{
  ?dish wdt:P31/wdt:P279* wd:Q746549 ;
        wdt:P495 ?country ;
        rdfs:label ?nameEn .
  FILTER(LANG(?nameEn) = "en")
  ?country wdt:P299 ?countryIso .
  OPTIONAL {{ ?dish rdfs:label ?nameIt . FILTER(LANG(?nameIt) = "it") }}
  OPTIONAL {{
    ?dish wdt:P527 ?ingredient .
    ?ingredient rdfs:label ?ingredientNameEn .
    FILTER(LANG(?ingredientNameEn) = "en")
  }}
}}
LIMIT {limit}
"""


@dataclass
class WikidataDish:
    qid: str
    name_en: str
    name_it: str | None
    country_code: str  # ISO 3166-1 numeric, zero-padded
    ingredient_names_en: list[str] = field(default_factory=list)


def build_query(limit: int = 500) -> str:
    return DISHES_QUERY.format(limit=limit)


def fetch_dishes(limit: int = 500, client: httpx.Client | None = None) -> list[WikidataDish]:
    """Query the live endpoint. Not used in tests: they parse a saved response instead."""
    owns_client = client is None
    client = client or httpx.Client(timeout=60)
    try:
        response = client.get(
            SPARQL_ENDPOINT,
            params={"query": build_query(limit), "format": "json"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
        return parse_response(response.json())
    finally:
        if owns_client:
            client.close()


def parse_response(payload: Mapping) -> list[WikidataDish]:
    """Group SPARQL result rows (one per dish/ingredient pair) into one entry per dish."""
    dishes: dict[str, WikidataDish] = {}
    for row in payload["results"]["bindings"]:
        qid = row["dish"]["value"].rsplit("/", 1)[-1]
        dish = dishes.get(qid)
        if dish is None:
            dish = dishes[qid] = WikidataDish(
                qid=qid,
                name_en=row["nameEn"]["value"],
                name_it=row.get("nameIt", {}).get("value"),
                country_code=row["countryIso"]["value"].zfill(3),
            )
        ingredient = row.get("ingredientNameEn", {}).get("value")
        if ingredient and ingredient not in dish.ingredient_names_en:
            dish.ingredient_names_en.append(ingredient)
    return list(dishes.values())
