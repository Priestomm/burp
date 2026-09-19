# mappetito

Una mappa del mondo per chi vive da solo: inserisci gli ingredienti che hai in casa e clicca su un paese. L'app ti propone un piatto **vegetariano o vegano** di quel paese, per **una porzione**, cucinabile con quello che hai, indicando cosa ti manca. I paesi sono colorati in base a quanto riesci a cucinare adesso.

> Stato: scheletro funzionante. I dati inclusi (5 paesi, 10 piatti) sono **dati di prova** (`source: "sample"`), non definitivi.

## Come funziona

- **Local-first**: nessun backend applicativo né database server. Le ricette sono file JSON statici; la dispensa, la dispensa base e la modalità (vegetariano/vegano) sono salvate sul dispositivo (IndexedDB, via Dexie).
- **Modalità**: di default l'app è *vegetariana* (mostra anche i piatti vegani). L'interruttore «Solo piatti vegani» restringe mappa e punteggi alle ricette vegane e ignora gli ingredienti non vegani della dispensa base.
- **Colori della mappa** (ogni livello ha anche una texture, quindi non dipende solo dal colore):
  - verde pieno: *posso cucinare* (nessun ingrediente essenziale mancante);
  - giallo a righe: *manca poco*;
  - arancio a puntini: *lontano*;
  - grigio: nessun piatto per la modalità scelta.
- **Piatti adattati**: le versioni vegetariane di piatti che in origine contengono carne o pesce sono segnalate come «Versione vegetariana di …» e non sono mai presentate come il piatto originale. A parità di punteggio, un piatto vegetariano per tradizione ha la precedenza su un adattamento.
- **Dieta calcolata, non dichiarata**: il campo `diet` di una ricetta non viene preso dalla fonte. La pipeline lo calcola dai flag degli ingredienti e **fallisce** se una ricetta contiene un ingrediente non vegetariano (salsa di pesce, acciughe, brodo di carne, gelatina, strutto, dashi con katsuobushi, Parmigiano Reggiano, Grana Padano…).

## Struttura

```
mappetito/
├── pipeline/   Python (uv): prepara offline il dataset e lo scrive in app/static/data/
├── app/        SvelteKit statico (adapter-static), TypeScript, PWA installabile
├── worker/     Cloudflare Worker (per ora solo stub)
└── .github/    CI: lint + test + build
```

### `pipeline/`

- `mappetito_pipeline/models.py`: modelli Pydantic (`Ingredient`, `RecipeIngredient`, `Recipe`), **unica fonte di verità** dello schema.
- `mappetito_pipeline/diet.py`: calcolo di `diet` e rifiuto degli ingredienti non vegetariani.
- `mappetito_pipeline/sources/`: `wikidata.py` (query SPARQL, testata su una risposta salvata) e `themealdb.py` (stub).
- `data/seed/`: dizionario degli ingredienti e ricette di prova.
- `build.py`: legge i dati, valida, calcola `diet`, scrive `recipes.json` e `ingredients.json`.
- `export_schema.py`: esporta il JSON Schema da Pydantic in `pipeline/schema/`.

### `app/`

- `src/lib/scoring.ts`: punteggio (funzione pura, testata). Gli ingredienti essenziali mancanti pesano 5, quelli opzionali 1; un paese prende il punteggio della sua ricetta migliore.
- `src/lib/matching.ts`: interfaccia `IngredientMatcher` con l'implementazione su id canonici e sinonimi.
- `src/lib/types/generated.ts`: tipi TypeScript **generati** dal JSON Schema (non modificare a mano).
- `src/lib/db.ts`: persistenza con Dexie.
- `src/service-worker.ts` e `static/manifest.webmanifest`: PWA, funziona offline.

## Requisiti

- [uv](https://docs.astral.sh/uv/) (Python ≥ 3.13)
- Node.js ≥ 22 e [pnpm](https://pnpm.io/)

## Avvio

```sh
# 1. Dati: genera app/static/data/*.json (già committati, serve solo se cambi i dati)
cd pipeline
uv sync
uv run python build.py

# 2. Tipi TypeScript: solo se cambi i modelli Pydantic
uv run python export_schema.py
cd ..
pnpm --filter app generate-types

# 3. App
pnpm install
pnpm dev            # http://localhost:5173
```

## Test e qualità

```sh
pnpm check                      # Biome (lint + formattazione JS/TS)
pnpm --filter app check         # svelte-check (tipi)
pnpm test                       # Vitest (scoring, ricerca)
pnpm build                      # build statica in app/build

cd pipeline
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

La CI (GitHub Actions) esegue tutto questo e verifica anche che dati e tipi generati siano aggiornati.

Nota: pnpm 10+ non esegue gli script di installazione delle dipendenze finché non li approvi. Per far girare `wrangler dev` nel worker serve `pnpm approve-builds`.

## Fonti dati previste

| Fonte | Uso previsto | Licenza |
| --- | --- | --- |
| [Wikidata](https://www.wikidata.org) | piatti con paese d'origine (P495) e ingredienti | CC0 |
| [TheMealDB](https://www.themealdb.com) | ricette con ingredienti e procedimento (stub) | da verificare prima dell'uso |
| [Wikibooks](https://it.wikibooks.org) (ricettari) | procedimenti | CC BY-SA |
| [Open Food Facts](https://world.openfoodfacts.org) | prodotti e ingredienti da scontrino | ODbL |
| [FoodKeeper](https://www.fsis.usda.gov/shared/data/EN/foodkeeper.json) (USDA) | durata di conservazione (`shelf_life_days`) | pubblico dominio (USDA) |
| [Natural Earth](https://www.naturalearthdata.com) (via `world-atlas`) | confini dei paesi | pubblico dominio |

Ogni ricetta riporta `source` e `license`; le ricette di prova hanno `source: "sample"`.

## Da fare (lasciato volutamente fuori dallo scheletro)

- OCR degli scontrini (`worker/`, `POST /receipt`).
- Embedding (Transformers.js) dietro `IngredientMatcher`, per riconoscere ingredienti simili.
- Notifiche di scadenza (handler cron del worker).
- Altre fonti dati (TheMealDB, Wikibooks, Open Food Facts, FoodKeeper) e curatela di un dataset vero.
- Nomi dei paesi in italiano e traduzione dei procedimenti (ora in inglese nei dati di prova).
