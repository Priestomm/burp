"""Maps free-text ingredient names to canonical ingredient ids.

Python counterpart of `app/src/lib/matching.ts` (same normalization and precedence): the
canonical id, `name_en` and `name_it` are registered first, and a synonym only if that
normalized name is not already claimed. Keep the two in sync.
"""

import re
import unicodedata
from collections.abc import Mapping

from mappetito_pipeline.models import Ingredient

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_name(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NON_WORD.sub(" ", stripped).strip()


class SynonymIndex:
    def __init__(self, ingredients: Mapping[str, Ingredient]) -> None:
        self._by_name: dict[str, str] = {}
        for item in ingredients.values():
            for name in (item.id.replace("_", " "), item.name_en, item.name_it):
                self._by_name.setdefault(normalize_name(name), item.id)
        for item in ingredients.values():
            for name in (*item.synonyms_en, *item.synonyms_it):
                self._by_name.setdefault(normalize_name(name), item.id)

    def resolve(self, *candidates: str) -> str | None:
        """Exact match on each candidate in order, then the longest known name inside one."""
        normalized = [normalize_name(c) for c in candidates if c]
        for name in normalized:
            if name in self._by_name:
                return self._by_name[name]
        for name in normalized:
            padded = f" {name} "
            hits = [key for key in self._by_name if key and f" {key} " in padded]
            if hits:
                return self._by_name[max(hits, key=len)]
        return None
