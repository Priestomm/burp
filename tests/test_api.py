import pytest
from fastapi.testclient import TestClient

from burp.api import create_app
from burp.catalog import SynonymIndex, load_ingredients
from burp.library import Library
from burp.models import ImportedRecipe
from tests.test_structure import ingredient, valid_recipe


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "burp.db"
    recipe = valid_recipe(
        title="Gnocchi di tofu gommosi glassati",
        nome_riga_1="Gnocchi",
        nome_riga_2="di tofu",
        descrittore="gommosi e glassati",
        servings=3,
        ingredients=[
            ingredient("tofu", "400g tofu vellutato", 400, "g"),
            ingredient("olio di sesamo", "3 cucchiai olio di sesamo", 3, "cucchiaio"),
            ingredient("limone", "Succo di limone qb", unit="q.b."),
            ingredient("cipollotto", "cipollotto per decorare"),
            ingredient("semi di sesamo", "semi di sesamo per decorare"),
        ],
        tags={"cuisine": "giapponese", "course": "antipasto", "diet": "vegan"},
        completeness={"status": "partial", "missing": ["quantità di cipollotto"]},
    )
    with Library(path, SynonymIndex(load_ingredients())) as lib:
        lib.add(ImportedRecipe(recipe=recipe, content_source="caption"))
        lib.add(ImportedRecipe(recipe=valid_recipe(steps=[]), content_source="caption"))
    return path


@pytest.fixture
def api(db):
    return TestClient(create_app(db))


def test_library_lists_recipes_with_what_is_left_to_clarify(api):
    items = api.get("/api/recipes").json()
    assert [(i["id"], i["nome_riga_1"], i["to_clarify"]) for i in items] == [
        (2, "Dal", 1),  # no steps
        (1, "Gnocchi", 2),  # cipollotto and sesamo
    ]
    assert items[1]["cooked"] == {"count": 0, "last": None}


def test_library_search_uses_free_words(api):
    assert [i["id"] for i in api.get("/api/recipes", params={"q": "vegana tofu"}).json()] == [1]


def test_recipe_detail_has_the_title_parts_and_the_quantity_states(api):
    recipe = api.get("/api/recipes/1").json()
    assert (recipe["nome_riga_1"], recipe["nome_riga_2"], recipe["descrittore"]) == (
        "Gnocchi",
        "di tofu",
        "gommosi e glassati",
    )
    assert [i["status"] for i in recipe["ingredients"]] == [
        "given",
        "given",
        "to_taste",
        "missing",
        "missing",
    ]
    assert recipe["ingredients"][1]["base_unit"] == "tsp"
    assert recipe["ingredients"][1]["base_quantity"] == 9
    assert recipe["still_missing"] == ["cipollotto", "semi di sesamo"]


def test_unknown_recipe_is_404(api):
    response = api.get("/api/recipes/99")
    assert response.status_code == 404
    assert "#99" in response.json()["detail"]


def test_write_a_quantity_then_take_it_back(api):
    recipe = api.put("/api/recipes/1/ingredients/3", json={"quantity": 1}).json()
    assert recipe["ingredients"][3]["status"] == "given"
    assert recipe["ingredients"][3]["edited"] is True
    assert recipe["still_missing"] == ["semi di sesamo"]
    recipe = api.delete("/api/recipes/1/ingredients/3/edit").json()
    assert recipe["ingredients"][3]["status"] == "missing"


def test_accept_quantities_by_eye(api):
    recipe = api.post("/api/recipes/1/by-eye", json={"indices": [3, 4]}).json()
    assert [i["status"] for i in recipe["ingredients"][3:]] == ["by_eye", "by_eye"]
    assert recipe["still_missing"] == []
    assert api.get("/api/recipes").json()[1]["to_clarify"] == 0


def test_bad_edits_are_rejected(api):
    assert api.put("/api/recipes/1/ingredients/9", json={"quantity": 1}).status_code == 404
    assert api.put("/api/recipes/1/ingredients/0", json={"quantity": 0}).status_code == 422
    assert api.post("/api/recipes/1/by-eye", json={"indices": []}).status_code == 422


def test_cooked_counts_and_shows_in_the_library(api):
    api.post("/api/recipes/1/cooked")
    cooked = api.post("/api/recipes/1/cooked").json()
    assert cooked["count"] == 2 and cooked["last"]
    assert api.get("/api/recipes").json()[1]["cooked"]["count"] == 2
    assert api.post("/api/recipes/99/cooked").status_code == 404


def test_the_schema_names_every_operation(api):
    schema = api.get("/api/openapi.json").json()
    operations = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert operations == {
        "listRecipes",
        "getRecipe",
        "setQuantity",
        "clearEdit",
        "markByEye",
        "markCooked",
    }


def test_parallel_requests_on_a_real_server(db):
    # The web app asks for the library and a recipe at the same time, and uvicorn may open the
    # SQLite connection in one worker thread and use it in another. TestClient does not show
    # this, so the test runs a real server.
    import socket
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    import httpx
    import uvicorn

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(db), port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        while not server.started:
            time.sleep(0.01)
        paths = ["/api/recipes", "/api/recipes/1"] * 20
        with ThreadPoolExecutor(max_workers=16) as pool:
            codes = list(
                pool.map(lambda p: httpx.get(f"http://127.0.0.1:{port}{p}").status_code, paths)
            )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    assert codes == [200] * len(paths)
