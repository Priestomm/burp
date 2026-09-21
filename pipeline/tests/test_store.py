from mappetito_pipeline.ingest.reconcile import reconcile
from mappetito_pipeline.ingest.store import Provenance, load_all, ready_drafts, save
from tests.test_reconcile import recipe


def test_save_and_load_round_trip(tmp_path, ingredients):
    imported = reconcile(recipe(), ingredients, Provenance(source="transcript", reason="x"))
    path = save(imported, tmp_path)
    assert path.name == "in-dal-tadka.json"
    assert load_all(tmp_path) == [imported]


def test_load_all_of_a_missing_directory_is_empty(tmp_path):
    assert load_all(tmp_path / "nope") == []


def test_only_ready_recipes_are_published(tmp_path, ingredients):
    ready = reconcile(recipe(), ingredients)
    review = reconcile(_low_confidence(), ingredients)
    save(ready, tmp_path)
    save(review, tmp_path)
    assert review.status == "needs_review"
    assert [d.id for d in ready_drafts(tmp_path)] == [ready.id]


def _low_confidence():
    return recipe(
        title="Fusion",
        origin={"country_iso2": "KR", "cuisine": "?", "confidence": 0.2, "reasoning": "?"},
    )


def test_build_publishes_ready_imports_and_skips_needs_review(tmp_path, ingredients):
    import json

    from build import build

    imported = tmp_path / "imported"
    ready = reconcile(recipe(), ingredients)
    save(ready, imported)
    save(reconcile(_low_confidence(), ingredients), imported)

    _, recipes = build(tmp_path / "out", imported_dir=imported)

    published = json.loads((tmp_path / "out" / "recipes.json").read_text())
    ids = {r["id"] for r in published}
    assert len(recipes) == len(published) == 11  # 10 seed + 1 ready import
    assert ready.id in ids
    assert "kr-fusion" not in ids
    assert next(r for r in published if r["id"] == ready.id)["diet"] == "vegan"
