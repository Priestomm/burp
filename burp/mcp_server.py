"""burp! as an MCP server: Claude, on the phone too, saves the recipes it writes and reads yours.

Three tools, none that deletes: `salva_ricetta` takes the recipe already structured by Claude
(the same `Recipe` schema as an import, through the same `finalize` rules, so no model call and
no cost here), `cerca_ricette` and `leggi_ricetta`.

Claude reaches the server from Anthropic's cloud, so it must be on a public HTTPS address
(BURP_MCP_URL, through a tunnel to this Mac) and it must ask who is calling. Claude connectors
sign in with OAuth: this module is also a small authorization server for one person. When the
connector is added, Claude registers itself (Dynamic Client Registration), sends you to a burp
page that asks for BURP_MCP_PASSWORD, and gets a token. Clients and tokens are kept in the
database (tokens hashed), so a restart does not sign you out.
"""

import asyncio
import hashlib
import hmac
import html
import json
import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from burp.catalog import SynonymIndex, load_ingredients
from burp.library import Library
from burp.models import ImportedRecipe, Recipe
from burp.render import full_text, one_line
from burp.structure import finalize
from burp.worker import INGREDIENTS

log = logging.getLogger(__name__)

SCOPE = "burp"
ACCESS_TTL = 24 * 3600  # Claude refreshes it with the refresh token
REFRESH_TTL = 180 * 24 * 3600  # about six months before signing in again
CODE_TTL = 300
LOGIN_TTL = 600
LOGIN_ATTEMPTS = 3
WRONG_PASSWORD_DELAY = 1.0
DEFAULT_PORT = 8001

INSTRUCTIONS = """\
burp! è la libreria personale di ricette dell'utente. Quando l'utente chiede di salvare una \
ricetta (per esempio una che gli hai appena scritto), usa salva_ricetta con la ricetta completa: \
ingredienti con quantità e unità, passaggi, porzioni e tempo se li conosci. Usa cerca_ricette e \
leggi_ricetta per rispondere su quello che l'utente ha già salvato."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class _Login:
    client_id: str
    params: AuthorizationParams
    expires_at: float
    attempts: int = 0


class BurpOAuth:
    """An OAuth authorization server for one person, who proves it with a password."""

    def __init__(self, db_path: Path | str, password: str, public_url: str) -> None:
        self.db_path, self.password, self.public_url = db_path, password, public_url
        self._logins: dict[str, _Login] = {}  # short-lived: a restart only asks to try again
        self._codes: dict[str, AuthorizationCode] = {}

    def _library(self) -> Library:
        return Library(self.db_path)

    # Clients

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with self._library() as lib:
            row = lib.conn.execute(
                "SELECT info FROM mcp_clients WHERE client_id = ?", (client_id,)
            ).fetchone()
        return OAuthClientInformationFull.model_validate_json(row["info"]) if row else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        with self._library() as lib, lib.conn:
            lib.conn.execute(
                "INSERT OR REPLACE INTO mcp_clients (client_id, info, created_at)"
                " VALUES (?, ?, datetime('now'))",
                (client_info.client_id, client_info.model_dump_json()),
            )

    # Signing in: /authorize sends the browser to the password page, which issues the code

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        self._forget_expired()
        request = secrets.token_urlsafe(24)
        self._logins[request] = _Login(client.client_id, params, time.time() + LOGIN_TTL)
        return f"{self.public_url}/login?r={request}"

    def login_page(self, request: str, error: str = "") -> HTMLResponse:
        if request not in self._logins:
            return _page("Richiesta scaduta: ricollega burp! da Claude e riprova.", status=400)
        message = f'<p class="error">{html.escape(error)}</p>' if error else ""
        return _page(
            f"""<p>Claude chiede di usare la tua libreria di ricette.</p>{message}
<form method="post" action="/login">
  <input type="hidden" name="r" value="{html.escape(request)}">
  <label for="p">Password di burp!</label>
  <input id="p" name="password" type="password" autocomplete="current-password" autofocus>
  <button type="submit">collega</button>
</form>""",
            status=401 if error else 200,
        )

    async def check_login(self, request: str, password: str) -> Response:
        login = self._logins.get(request)
        if login is None or login.expires_at < time.time():
            self._logins.pop(request, None)
            return self.login_page(request)
        if not hmac.compare_digest(password.encode(), self.password.encode()):
            await asyncio.sleep(WRONG_PASSWORD_DELAY)  # guessing many passwords takes forever
            login.attempts += 1
            log.warning("mcp: wrong password (%d of %d)", login.attempts, LOGIN_ATTEMPTS)
            if login.attempts >= LOGIN_ATTEMPTS:
                del self._logins[request]
                return _page("Password sbagliata troppe volte: ricollega burp! da Claude.", 403)
            return self.login_page(request, "Password sbagliata.")
        del self._logins[request]
        code = secrets.token_urlsafe(32)
        params = login.params
        self._codes[code] = AuthorizationCode(
            code=code,
            scopes=params.scopes or [SCOPE],
            expires_at=time.time() + CODE_TTL,
            client_id=login.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
            subject="me",
        )
        log.info("mcp: signed in, client %s", login.client_id)
        target = construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)
        return RedirectResponse(target, status_code=302)

    def _forget_expired(self) -> None:
        now = time.time()
        self._logins = {k: v for k, v in self._logins.items() if v.expires_at > now}
        self._codes = {k: v for k, v in self._codes.items() if v.expires_at > now}

    # Codes and tokens

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self._codes.get(authorization_code)
        if code is None or code.client_id != client.client_id or code.expires_at < time.time():
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if self._codes.pop(authorization_code.code, None) is None:
            raise TokenError("invalid_grant", "code already used")
        return self._issue(client.client_id, authorization_code.scopes, authorization_code.resource)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        row = self._token(refresh_token, "refresh")
        if row is None or row["client_id"] != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=row["client_id"],
            scopes=json.loads(row["scopes"]),
            expires_at=row["expires_at"],
            resource=row["resource"],
            subject="me",
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        with self._library() as lib, lib.conn:  # one use only: a stolen old one is worthless
            lib.conn.execute(
                "DELETE FROM mcp_tokens WHERE token_hash = ?", (_hash(refresh_token.token),)
            )
        return self._issue(client.client_id, scopes or refresh_token.scopes, refresh_token.resource)

    async def load_access_token(self, token: str) -> AccessToken | None:
        row = self._token(token, "access")
        if row is None:
            return None
        return AccessToken(
            token=token,
            client_id=row["client_id"],
            scopes=json.loads(row["scopes"]),
            expires_at=row["expires_at"],
            resource=row["resource"],
            subject="me",
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        with self._library() as lib, lib.conn:
            lib.conn.execute("DELETE FROM mcp_tokens WHERE token_hash = ?", (_hash(token.token),))

    def _issue(self, client_id: str, scopes: list[str], resource: str | None) -> OAuthToken:
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = int(time.time())
        with self._library() as lib, lib.conn:
            for token, kind, ttl in (
                (access, "access", ACCESS_TTL),
                (refresh, "refresh", REFRESH_TTL),
            ):
                lib.conn.execute(
                    "INSERT INTO mcp_tokens (token_hash, kind, client_id, scopes, expires_at,"
                    " resource) VALUES (?, ?, ?, ?, ?, ?)",
                    (_hash(token), kind, client_id, json.dumps(scopes), now + ttl, resource),
                )
            lib.conn.execute("DELETE FROM mcp_tokens WHERE expires_at < ?", (now,))
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TTL,
            refresh_token=refresh,
            scope=" ".join(scopes),
        )

    def _token(self, token: str, kind: str):
        with self._library() as lib:
            row = lib.conn.execute(
                "SELECT client_id, scopes, expires_at, resource FROM mcp_tokens"
                " WHERE token_hash = ? AND kind = ?",
                (_hash(token), kind),
            ).fetchone()
        if row is None or (row["expires_at"] is not None and row["expires_at"] < time.time()):
            return None
        return row


def _page(body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>burp!</title>
<style>
body {{ margin: 0; min-height: 100dvh; background: #ffd13b; color: #161311;
  font: 17px/1.4 system-ui, sans-serif; display: grid; place-items: center; padding: 16px; }}
main {{ max-width: 360px; width: 100%; }}
h1 {{ font: 900 64px/0.8 "Arial Black", system-ui, sans-serif; margin: 0 0 24px; }}
label {{ display: block; font-weight: 700; margin: 16px 0 6px; }}
input {{ width: 100%; box-sizing: border-box; padding: 12px; font: inherit;
  border: 2px solid #161311; background: #fbfaf5; }}
button {{ margin-top: 12px; padding: 12px 20px; font: inherit; font-weight: 700;
  background: #161311; color: #ffd13b; border: 0; text-transform: uppercase; }}
.error {{ color: #a1150c; font-weight: 700; }}
</style></head><body><main><h1>burp!</h1>{body}</main></body></html>""",
        status_code=status,
    )


def create_server(
    db_path: Path | str,
    public_url: str,
    password: str,
    catalog: SynonymIndex | None = None,
) -> tuple[MCPServer, BurpOAuth]:
    catalog = catalog or SynonymIndex(load_ingredients())
    oauth = BurpOAuth(db_path, password, public_url)
    server = MCPServer(
        name="burp",
        title="burp!",
        instructions=INSTRUCTIONS,
        auth_server_provider=oauth,
        auth=AuthSettings(
            issuer_url=public_url,
            resource_server_url=f"{public_url}/mcp",
            validate_token_resource=False,  # one resource only; the token store says what's valid
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=[SCOPE],
        ),
    )

    @server.custom_route("/login", methods=["GET"], include_in_schema=False)
    async def login_form(request: Request) -> Response:
        return oauth.login_page(request.query_params.get("r", ""))

    @server.custom_route("/login", methods=["POST"], include_in_schema=False)
    async def login_submit(request: Request) -> Response:
        form = await request.form()
        return await oauth.check_login(str(form.get("r", "")), str(form.get("password", "")))

    @server.tool()
    def salva_ricetta(ricetta: Recipe) -> str:
        """Salva una ricetta nella libreria burp! dell'utente. Passa la ricetta completa e già
        strutturata, in italiano: ingredienti con quantità e unità (q.b. dove serve), passaggi,
        porzioni e tempo se li conosci. Le regole dei campi sono nelle loro descrizioni."""
        recipe = finalize(ricetta, catalog)
        imported = ImportedRecipe(
            recipe=recipe, content_source="chat", content_reason="scritta con Claude"
        )
        with Library(db_path, catalog) as lib:
            saved, _ = lib.add(imported)
            lib.enqueue(INGREDIENTS, saved.id, [])  # their pictures, when the worker runs
        missing = recipe.completeness.missing
        note = f" Mancano: {', '.join(missing)}." if missing else ""
        return f"Salvata in burp! come ricetta N° {saved.id}: {recipe.title}.{note}"

    @server.tool()
    def cerca_ricette(parole: str = "") -> str:
        """Cerca nella libreria burp! dell'utente: ogni parola deve comparire nel titolo, nei
        tag (cucina, portata, dieta) o negli ingredienti. Senza parole elenca tutte le ricette."""
        with Library(db_path, catalog) as lib:
            found = lib.search(text=parole)
        if not found:
            return "Nessuna ricetta trovata."
        return "\n".join(one_line(saved, pad=False) for saved in found)

    @server.tool()
    def leggi_ricetta(numero: int) -> str:
        """La ricetta completa con quel numero (N°), con ingredienti, dosi e passaggi."""
        with Library(db_path, catalog) as lib:
            saved = lib.get(numero)
        return full_text(saved) if saved else f"Non c'è nessuna ricetta N° {numero}."

    return server, oauth


def create_app(db_path: Path | str, public_url: str, password: str) -> Starlette:
    server, _ = create_server(db_path, public_url, password)
    public_host = urlsplit(public_url).netloc
    return server.streamable_http_app(
        # Requests come through the tunnel with the public host name; locally for tests.
        transport_security=TransportSecuritySettings(
            allowed_hosts=[public_host, "127.0.0.1:*", "localhost:*"],
            allowed_origins=[
                public_url,
                "https://claude.ai",
                "http://127.0.0.1:*",
                "http://localhost:*",
            ],
        ),
    )
