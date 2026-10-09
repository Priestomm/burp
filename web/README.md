# burp! · web

The web app of burp!: Next.js 16 (App Router, Server Components, Cache Components), React 19, TypeScript, CSS Modules.

Pages read from the Python API on the server (`src/lib/api/server.ts`), and changes go through Server Actions: the browser only ever talks to Next.js. The API types are generated from its OpenAPI schema, so the Pydantic models stay the single source of truth.

```sh
# from the repository root
uv run burp dev                   # API, bot and this app together

# or this app alone, with the API running on http://127.0.0.1:8000
pnpm install
pnpm dev                          # http://localhost:3000
pnpm gen:api                      # regenerate the API types after changing the Pydantic models
pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

`BURP_API_URL` changes the API's address (default `http://127.0.0.1:8000`).

The page is in `src/components/zine/`, the marker notes generated from the data in `src/components/marker/`, and the pure logic (dose scaling, the dose table, time and temperature marks, Italian wording, marker geometry) in `src/lib/`, each with its tests. The first design, with stickers, is in git: `git checkout tema-adesivi`.
