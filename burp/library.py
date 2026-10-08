"""The personal recipe library: a SQLite file, searchable by title, tag and ingredient.

Each recipe is stored whole as JSON, plus a few normalized columns and one row per canonical
ingredient name to search on. The same post shared twice is saved once: `source_key` (see
ingest.source_key) is unique, so a /p/ and a /reel/ link of the same post count as one.
"""

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from burp.catalog import SynonymIndex, normalize_name
from burp.config import DEFAULT_DB_PATH
from burp.ingest import source_key
from burp.models import ImportedRecipe, IngredientEdit, Recipe
from burp.structure import deduplicate_missing

# Diet tags can be searched with their Italian names too.
DIET_ALIASES = {
    "vegana": "vegan",
    "vegano": "vegan",
    "vegetariana": "vegetarian",
    "vegetariano": "vegetarian",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY,
    source_key TEXT UNIQUE,
    title TEXT NOT NULL,
    title_norm TEXT NOT NULL,
    cuisine TEXT,
    course TEXT,
    diet TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS recipe_ingredients_name ON recipe_ingredients(name);
"""

# Applied in order to databases older than them; PRAGMA user_version is the current index.
MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS cooked (
        recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
        cooked_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS cooked_recipe ON cooked(recipe_id);
    """,
]


@dataclass(frozen=True)
class Cooked:
    count: int
    last: str | None  # ISO timestamp of the last time, None if never


@dataclass(frozen=True)
class SavedRecipe:
    id: int
    created_at: str
    imported: ImportedRecipe

    @property
    def recipe(self) -> Recipe:
        return self.imported.recipe


class Library:
    def __init__(self, path: Path | str = DEFAULT_DB_PATH, catalog: SynonymIndex | None = None):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.catalog = catalog
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
            with self.conn:
                self.conn.executescript(script)
                if number == 1:
                    self._upgrade_recipes_v1()
                self.conn.execute(f"PRAGMA user_version = {number}")

    def _upgrade_recipes_v1(self) -> None:
        """Recipes saved before the title split: the whole title becomes the first line (run
        `burp backfill-titles` to split it properly), and repeated missing items go."""
        for row in self.conn.execute("SELECT id, data FROM recipes").fetchall():
            data = json.loads(row["data"])
            recipe = data["recipe"]
            recipe.setdefault("nome_riga_1", recipe["title"])
            missing = recipe["completeness"]["missing"]
            recipe["completeness"]["missing"] = deduplicate_missing(missing)
            self.conn.execute(
                "UPDATE recipes SET data = ? WHERE id = ?",
                (ImportedRecipe.model_validate(data).model_dump_json(), row["id"]),
            )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Library":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def add(self, imported: ImportedRecipe) -> tuple[SavedRecipe, bool]:
        """Save a recipe. If its post is already in the library, return that one instead.

        Returns (recipe in the library, True if it was just added)."""
        recipe = imported.recipe
        key = source_key(recipe.source_url) if recipe.source_url else None
        if key and (existing := self._one("source_key = ?", key)):
            return existing, False
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO recipes (source_key, title, title_norm, cuisine, course, diet, data,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    recipe.title,
                    normalize_name(recipe.title),
                    normalize_name(recipe.tags.cuisine or ""),
                    normalize_name(recipe.tags.course or ""),
                    recipe.tags.diet,
                    imported.model_dump_json(),
                    created_at,
                ),
            )
            self.conn.executemany(
                "INSERT INTO recipe_ingredients (recipe_id, name) VALUES (?, ?)",
                [(cursor.lastrowid, normalize_name(i.canonical_name)) for i in recipe.ingredients],
            )
        return SavedRecipe(cursor.lastrowid, created_at, imported), True

    def get(self, recipe_id: int) -> SavedRecipe | None:
        return self._one("id = ?", recipe_id)

    def find_by_url(self, url: str) -> SavedRecipe | None:
        return self._one("source_key = ?", source_key(url))

    def replace(self, recipe_id: int, imported: ImportedRecipe) -> SavedRecipe:
        """Store a changed version of a recipe (same post, same id)."""
        with self.conn:
            changed = self.conn.execute(
                "UPDATE recipes SET data = ?, title = ?, title_norm = ? WHERE id = ?",
                (
                    imported.model_dump_json(),
                    imported.recipe.title,
                    normalize_name(imported.recipe.title),
                    recipe_id,
                ),
            ).rowcount
        if not changed:
            raise KeyError(recipe_id)
        return self.get(recipe_id)

    def set_quantity(
        self, recipe_id: int, index: int, quantity: float, unit: str | None
    ) -> SavedRecipe:
        """ "Li scrivo io": the user fills in a quantity the post did not give."""
        return self._edit(recipe_id, index, IngredientEdit(quantity=quantity, unit=unit))

    def mark_by_eye(self, recipe_id: int, indices: Iterable[int]) -> SavedRecipe:
        """ "Sì, a occhio": these quantities stay unknown, and that is fine."""
        saved = self._require(recipe_id)
        edits = dict(saved.imported.edits)
        for index in indices:
            self._check_index(saved, index)
            edits[index] = IngredientEdit(by_eye=True)
        return self.replace(recipe_id, saved.imported.model_copy(update={"edits": edits}))

    def clear_edit(self, recipe_id: int, index: int) -> SavedRecipe:
        saved = self._require(recipe_id)
        edits = {i: e for i, e in saved.imported.edits.items() if i != index}
        return self.replace(recipe_id, saved.imported.model_copy(update={"edits": edits}))

    def cook(self, recipe_id: int) -> Cooked:
        """ "L'ho cucinata": one more time, now."""
        self._require(recipe_id)
        with self.conn:
            self.conn.execute(
                "INSERT INTO cooked (recipe_id, cooked_at) VALUES (?, ?)",
                (recipe_id, datetime.now(UTC).isoformat(timespec="seconds")),
            )
        return self.cooked(recipe_id)

    def cooked(self, recipe_id: int) -> Cooked:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n, MAX(cooked_at) AS last FROM cooked WHERE recipe_id = ?",
            (recipe_id,),
        ).fetchone()
        return Cooked(row["n"], row["last"])

    def cooked_all(self) -> dict[int, Cooked]:
        """Cooked counts of every recipe that was cooked at least once."""
        rows = self.conn.execute(
            "SELECT recipe_id, COUNT(*) AS n, MAX(cooked_at) AS last FROM cooked GROUP BY recipe_id"
        )
        return {row["recipe_id"]: Cooked(row["n"], row["last"]) for row in rows}

    def _edit(self, recipe_id: int, index: int, edit: IngredientEdit) -> SavedRecipe:
        saved = self._require(recipe_id)
        self._check_index(saved, index)
        edits = {**saved.imported.edits, index: edit}
        return self.replace(recipe_id, saved.imported.model_copy(update={"edits": edits}))

    def _require(self, recipe_id: int) -> SavedRecipe:
        saved = self.get(recipe_id)
        if saved is None:
            raise KeyError(recipe_id)
        return saved

    @staticmethod
    def _check_index(saved: SavedRecipe, index: int) -> None:
        if not 0 <= index < len(saved.recipe.ingredients):
            raise IndexError(f"recipe #{saved.id} has no ingredient {index}")

    def delete(self, recipe_id: int) -> bool:
        with self.conn:
            return self.conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,)).rowcount > 0

    def search(
        self,
        title: str | None = None,
        tags: Iterable[str] = (),
        ingredients: Iterable[str] = (),
        text: str | None = None,
    ) -> list[SavedRecipe]:
        """Recipes matching every given filter, newest first. No filter lists everything.

        - title: every word contained in the title, ignoring case and accents;
        - tags: each one equal to the cuisine, the course or the diet ("vegana" works too);
        - ingredients: each one in the recipe, by canonical name ("pomodori", "tomato" and
          "pomodoro" are the same) or as part of one ("pecorino" finds "pecorino romano");
        - text: free words, as typed in a chat. Each word must be in the title, the tags or
          the ingredients: "vegana ceci" finds vegan recipes with chickpeas.
        """
        clauses: list[tuple[str, list[str]]] = []
        clauses += [self._title(word) for word in normalize_name(title or "").split()]
        clauses += [self._tag(tag) for tag in tags]
        clauses += [self._ingredient(name) for name in ingredients]
        for word in normalize_name(text or "").split():
            options = [self._title(word), self._tag(word, partial=True), self._ingredient(word)]
            sql = " OR ".join(option for option, _ in options)
            clauses.append((f"({sql})", [p for _, params in options for p in params]))
        where = " AND ".join(sql for sql, _ in clauses) or "1"
        return self._many(where, *(p for _, params in clauses for p in params))

    @staticmethod
    def _title(word: str) -> tuple[str, list[str]]:
        return "title_norm LIKE ?", [f"%{word}%"]

    @staticmethod
    def _tag(tag: str, partial: bool = False) -> tuple[str, list[str]]:
        norm = normalize_name(tag)
        diet = DIET_ALIASES.get(norm, norm)
        if partial:  # a single typed word can be part of a course ("unico" in "piatto unico")
            return "(cuisine LIKE ? OR course LIKE ? OR diet = ?)", [f"%{norm}%"] * 2 + [diet]
        return "(cuisine = ? OR course = ? OR diet = ?)", [norm, norm, diet]

    def _ingredient(self, name: str) -> tuple[str, list[str]]:
        canonical = normalize_name(self.catalog.canonical_name(name) if self.catalog else name)
        sql = "id IN (SELECT recipe_id FROM recipe_ingredients WHERE name = ? OR name LIKE ?)"
        return sql, [canonical, f"%{normalize_name(name)}%"]

    def _one(self, where: str, *params) -> SavedRecipe | None:
        found = self._many(where, *params)
        return found[0] if found else None

    def _many(self, where: str, *params) -> list[SavedRecipe]:
        rows = self.conn.execute(
            f"SELECT id, created_at, data FROM recipes WHERE {where} ORDER BY id DESC", params
        )
        return [_saved(row) for row in rows]


def _saved(row: sqlite3.Row) -> SavedRecipe:
    imported = ImportedRecipe.model_validate_json(row["data"])
    return SavedRecipe(row["id"], row["created_at"], imported)
