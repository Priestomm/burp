# burp! · web

La web app di burp!: Next.js (App Router, Server Components), TypeScript, CSS Modules.

Le pagine leggono dall'API Python lato server (`src/lib/api/server.ts`) e le modifiche passano da Server Actions: il browser parla solo con Next.js. I tipi dell'API sono generati dal suo schema OpenAPI, quindi i modelli Pydantic restano l'unica fonte.

```sh
# dalla radice della repo, in un altro terminale
uv run burp serve                 # API su http://127.0.0.1:8000

cd web
pnpm install
pnpm dev                          # http://localhost:3000
pnpm gen:api                      # rigenera i tipi quando cambiano i modelli Pydantic
pnpm test && pnpm typecheck && pnpm lint
```

`BURP_API_URL` cambia l'indirizzo dell'API (default `http://127.0.0.1:8000`).

La pagina è in `src/components/zine/`; le note a pennarello generate dai dati sono in `src/components/marker/`. Il primo design, a adesivi, è nella storia di git: `git checkout tema-adesivi`.
