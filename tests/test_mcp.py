import asyncio
import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from burp.library import Library
from burp.mcp_server import create_app, create_server
from burp.models import ImportedRecipe
from tests.test_structure import ingredient, valid_recipe

URL = "http://localhost:8001"
PASSWORD = "cavolo-nero-42"
CALLBACK = "https://claude.ai/api/mcp/auth_callback"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
STREAM = {"accept": "application/json, text/event-stream"}


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr("burp.mcp_server.WRONG_PASSWORD_DELAY", 0)


@pytest.fixture
def db(tmp_path, catalog):
    path = tmp_path / "burp.db"
    with Library(path, catalog) as lib:
        lib.add(ImportedRecipe(recipe=valid_recipe(title="Pasta e ceci"), content_source="caption"))
    return path


def sign_in(client: TestClient) -> dict:
    """What Claude does when the connector is added, and the person types the password."""
    registered = client.post(
        "/register",
        json={
            "redirect_uris": [CALLBACK],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "client_name": "Claude",
        },
    )
    assert registered.status_code == 201, registered.text
    client_id = registered.json()["client_id"]
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    authorize = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": CALLBACK,
            "code_challenge": challenge.decode().rstrip("="),
            "code_challenge_method": "S256",
            "state": "s1",
            "resource": f"{URL}/mcp",
        },
        follow_redirects=False,
    )
    login = urlsplit(authorize.headers["location"])
    assert login.path == "/login"
    request = parse_qs(login.query)["r"][0]
    assert "Password di burp!" in client.get(f"/login?r={request}").text

    wrong = client.post("/login", data={"r": request, "password": "no"}, follow_redirects=False)
    assert wrong.status_code == 401 and "Password sbagliata" in wrong.text
    right = client.post("/login", data={"r": request, "password": PASSWORD}, follow_redirects=False)
    assert right.status_code == 302
    back = urlsplit(right.headers["location"])
    assert f"{back.scheme}://{back.netloc}{back.path}" == CALLBACK
    query = parse_qs(back.query)
    assert query["state"] == ["s1"]

    token = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": CALLBACK,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert token.status_code == 200, token.text
    return {**token.json(), "client_id": client_id}


def test_claude_signs_in_with_the_password_and_then_calls_the_tools(db):
    with TestClient(create_app(db, URL, PASSWORD), base_url=URL) as client:
        anonymous = client.post("/mcp", json=INITIALIZE, headers=STREAM)
        assert anonymous.status_code == 401
        assert "resource_metadata" in anonymous.headers["www-authenticate"]
        metadata = client.get("/.well-known/oauth-authorization-server").json()
        assert metadata["registration_endpoint"] == f"{URL}/register"

        tokens = sign_in(client)
        bearer = {**STREAM, "authorization": f"Bearer {tokens['access_token']}"}
        assert client.post("/mcp", json=INITIALIZE, headers=bearer).status_code == 200

        refreshed = client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": tokens["client_id"],
            },
        )
        assert refreshed.status_code == 200
        again = client.post(  # a refresh token works once
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": tokens["client_id"],
            },
        )
        assert again.status_code == 400

    # A restart of burp does not sign Claude out.
    with TestClient(create_app(db, URL, PASSWORD), base_url=URL) as client:
        bearer = {**STREAM, "authorization": f"Bearer {refreshed.json()['access_token']}"}
        assert client.post("/mcp", json=INITIALIZE, headers=bearer).status_code == 200
        forged = {**STREAM, "authorization": "Bearer not-a-token"}
        assert client.post("/mcp", json=INITIALIZE, headers=forged).status_code == 401


def test_three_wrong_passwords_end_the_attempt(db):
    with TestClient(create_app(db, URL, PASSWORD), base_url=URL) as client:
        client_id = client.post(
            "/register", json={"redirect_uris": [CALLBACK], "token_endpoint_auth_method": "none"}
        ).json()["client_id"]
        location = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": CALLBACK,
                "code_challenge": "x" * 43,
                "code_challenge_method": "S256",
            },
            follow_redirects=False,
        ).headers["location"]
        request = parse_qs(urlsplit(location).query)["r"][0]
        for _ in range(2):
            client.post("/login", data={"r": request, "password": "no"})
        assert client.post("/login", data={"r": request, "password": "no"}).status_code == 403
        late = client.post(
            "/login", data={"r": request, "password": PASSWORD}, follow_redirects=False
        )
        assert late.status_code == 400  # the right password, too late


def call(server, tool: str, arguments: dict) -> str:
    result = asyncio.run(server.call_tool(tool, arguments))
    assert not result.is_error, result.content
    return "".join(block.text for block in result.content)


def test_a_recipe_written_with_claude_is_saved_checked_and_found(db, catalog):
    server, _ = create_server(db, URL, PASSWORD, catalog)
    recipe = valid_recipe(
        title="Spaghetti burro e acciughe",
        ingredients=[
            ingredient("spaghetti", "200 g di spaghetti", 200, "g"),
            ingredient("acciuga", "acciughe"),  # no quantity: the rules notice
        ],
        tags={"cuisine": "italiana", "course": "primo", "diet": "vegan"},  # wrong: anchovies
    )
    answer = call(server, "salva_ricetta", {"ricetta": recipe.model_dump()})
    assert answer.startswith("Salvata in burp! come ricetta N° 2: Spaghetti burro e acciughe.")
    assert "quantità di acciuga" in answer

    with Library(db, catalog) as lib:
        saved = lib.get(2)
        assert saved.imported.content_source == "chat"
        assert saved.recipe.tags.diet == "neither"  # finalize, as for an import
        assert [job.kind for job in lib.jobs(2)] == ["ingredients"]

    assert "Spaghetti burro e acciughe" in call(server, "cerca_ricette", {"parole": "spaghetti"})
    assert "Pasta e ceci" in call(server, "cerca_ricette", {})
    assert "200 g" in call(server, "leggi_ricetta", {"numero": 2})
    assert "Non c'è nessuna ricetta N° 9" in call(server, "leggi_ricetta", {"numero": 9})
